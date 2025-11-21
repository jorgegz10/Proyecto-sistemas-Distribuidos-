import os
import os
import time
import psycopg2
import subprocess
import logging
from datetime import datetime

# Configuration
PRIMARY_HOST = os.getenv("PRIMARY_HOST", "postgres_primary")
PRIMARY_PORT = int(os.getenv("PRIMARY_PORT", "5432"))
REPLICA_HOST = os.getenv("REPLICA_HOST", "postgres_replica")
REPLICA_PORT = int(os.getenv("REPLICA_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "library")
DB_USER = os.getenv("DB_USER", "app")
DB_PASS = os.getenv("DB_PASS", "app")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "10"))
FAILOVER_COOLDOWN = int(os.getenv("FAILOVER_COOLDOWN", "300"))

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Global state
last_failover_time = None
primary_is_down = False
failover_executed = False

def check_primary_health():
    """Check if primary is reachable and writable."""
    try:
        conn = psycopg2.connect(
            host=PRIMARY_HOST,
            port=PRIMARY_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            connect_timeout=5
        )
        with conn.cursor() as cur:
            cur.execute("SELECT pg_is_in_recovery();")
            is_recovery = cur.fetchone()[0]
        conn.close()
        if is_recovery:
            logging.warning(f"{PRIMARY_HOST} is in recovery (not primary)")
            return False
        logging.debug(f"{PRIMARY_HOST} is healthy")
        return True
    except Exception as e:
        logging.error(f"Error connecting to {PRIMARY_HOST}:{PRIMARY_PORT}: {e}")
        return False

def check_replica_health():
    """Check if replica is reachable."""
    try:
        conn = psycopg2.connect(
            host=REPLICA_HOST,
            port=REPLICA_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            connect_timeout=5
        )
        conn.close()
        logging.debug(f"{REPLICA_HOST} is available")
        return True
    except Exception as e:
        logging.error(f"Replica not available: {e}")
        return False

def execute_failover():
    """Promote replica to primary."""
    global last_failover_time, failover_executed
    logging.warning("Starting failover process...")
    try:
        # Connect to replica
        conn = psycopg2.connect(
            host=REPLICA_HOST,
            port=REPLICA_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            connect_timeout=5
        )
        promote_command = f"docker exec {REPLICA_HOST} su - postgres -c '/usr/lib/postgresql/16/bin/pg_ctl promote -D /var/lib/postgresql/data'"
        logging.info("Executing promotion command...")
        result = subprocess.run(
            promote_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            logging.info("Promotion command succeeded")
            time.sleep(5)
            # Verify promotion
            conn_check = psycopg2.connect(
                host=REPLICA_HOST,
                port=REPLICA_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                connect_timeout=5
            )
            with conn_check.cursor() as cur:
                cur.execute("SELECT pg_is_in_recovery();")
                still_recovery = cur.fetchone()[0]
            conn_check.close()
            if not still_recovery:
                logging.info("FAILOVER SUCCESSFUL: Replica promoted to primary")
                last_failover_time = datetime.now()
                failover_executed = True
                return True
            else:
                logging.error("Failover failed: replica still in recovery")
                return False
        else:
            logging.error(f"Promotion error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logging.error("Promotion command timeout")
        return False
    except Exception as e:
        logging.error(f"Failover error: {e}")
        return False

def main():
    global primary_is_down, failover_executed
    logging.info("Starting PostgreSQL Failover Monitor")
    consecutive_failures = 0
    FAILURE_THRESHOLD = 3
    while True:
        try:
            if failover_executed:
                if check_replica_health():
                    logging.info(f"New primary ({REPLICA_HOST}) operational")
                else:
                    logging.error("Critical: New primary not responding!")
                time.sleep(CHECK_INTERVAL * 2)
                continue
            primary_healthy = check_primary_health()
            if primary_healthy:
                if primary_is_down:
                    logging.info("Primary recovered")
                    primary_is_down = False
                    consecutive_failures = 0
            else:
                consecutive_failures += 1
                logging.warning(f"Primary not responding (attempt {consecutive_failures}/{FAILURE_THRESHOLD})")
                if consecutive_failures >= FAILURE_THRESHOLD:
                    if not primary_is_down:
                        logging.error("PRIMARY DECLARED DOWN")
                        primary_is_down = True
                    if last_failover_time:
                        elapsed = (datetime.now() - last_failover_time).total_seconds()
                        if elapsed < FAILOVER_COOLDOWN:
                            logging.warning("Failover in cooldown")
                            time.sleep(CHECK_INTERVAL)
                            continue
                    if check_replica_health():
                        logging.warning("Initiating automatic failover...")
                        if execute_failover():
                            logging.info("FAILOVER COMPLETED SUCCESSFULLY")
                        else:
                            logging.error("Failover failed, will retry next cycle")
                    else:
                        logging.error("Replica unavailable, cannot failover")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logging.info("Monitor stopped by user")
            break
        except Exception as e:
            logging.error(f"Main loop error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
