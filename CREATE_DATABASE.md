# Creating the New Database: teststep_rag_bgem3

## Method 1: Using psql (if PostgreSQL is installed)

Find your PostgreSQL installation and use the full path:

### Windows (typical locations):
```powershell
# Option A: If PostgreSQL is in Program Files
& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -c "CREATE DATABASE teststep_rag_bgem3;"

# Option B: If PostgreSQL is in a different version folder (14, 13, etc.)
& "C:\Program Files\PostgreSQL\14\bin\psql.exe" -U postgres -c "CREATE DATABASE teststep_rag_bgem3;"

# Option C: If psql is in your PATH, just:
psql -U postgres -c "CREATE DATABASE teststep_rag_bgem3;"
```

### If it asks for password:
You'll be prompted for the password (from config.yaml: `123456`)

## Method 2: Using pgAdmin (GUI)

1. Open **pgAdmin**
2. Connect to your PostgreSQL server (localhost:5432)
3. Right-click on **Databases** → **Create** → **Database**
4. Name: `teststep_rag_bgem3`
5. Click **Save**

## Method 3: Using Python (if psql not available)

Create a temporary Python script:

```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="postgres",  # Connect to default postgres DB
    user="postgres",
    password="123456"
)
conn.autocommit = True

cur = conn.cursor()
cur.execute("CREATE DATABASE teststep_rag_bgem3;")
print("Database 'teststep_rag_bgem3' created successfully!")
cur.close()
conn.close()
```

Run it:
```bash
python create_db_temp.py
```

## Method 4: Using SQL File

Create a file `create_db.sql`:
```sql
CREATE DATABASE teststep_rag_bgem3;
```

Then run (if you have psql):
```bash
psql -U postgres -f create_db.sql
```

## Verify Database Created

After creation, verify it exists:

```sql
-- Connect to postgres database
psql -U postgres -d postgres

-- List databases
\l

-- You should see teststep_rag_bgem3 in the list
```

Or using Python:
```python
import psycopg2
conn = psycopg2.connect(host="localhost", port=5432, database="postgres", user="postgres", password="123456")
cur = conn.cursor()
cur.execute("SELECT datname FROM pg_database WHERE datname = 'teststep_rag_bgem3';")
result = cur.fetchone()
if result:
    print("✓ Database exists!")
else:
    print("✗ Database not found")
```

## Next Steps

Once the database is created:

1. **Verify config.yaml** has the correct database name:
   ```yaml
   database:
     database: "teststep_rag_bgem3"
   ```

2. **Run ingestion**:
   ```bash
   python main.py --mode ingest --input "csv files/Already_Automated_Tests_nrm.csv"
   ```

   This will automatically:
   - Create the pgvector extension
   - Create all necessary tables
   - Set up indexes

