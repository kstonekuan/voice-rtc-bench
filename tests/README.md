# Tests

## Running Tests

From the repository root, run:

```bash
uv run python tests/test_influxdb_connection.py
```

## Available Tests

### test_influxdb_connection.py

Comprehensive test for InfluxDB (Amazon Timestream for InfluxDB 3) connection and operations.

**Tests:**
1. Query recent results from database
2. Query aggregated statistics
3. Write test data points
4. Verify written data can be queried back

**Requirements:**
- `.env` file with proper InfluxDB credentials
- Network access to InfluxDB instance
- Security group configured to allow inbound traffic on port 8181
