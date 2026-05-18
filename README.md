# data-analysis-agent - Open Source Local Data Analysis Assistant.



# Key Features

- 📊 Data visualization    
-  🚀 Table joins
-  📈 Run statistical tests directly on your dataset
-  📂 Unlimited rows, 30+ tables analyzed simultaneously
-  🐍 Built-in python sandbox
-  🦙 Ollama integration
and more..

16GB RAM is enough for practical performance using [Lightning-4b](https://data-analysis-agent.com/lightning-4b)

# Quick Start

Introduce you how to run **data-analysis-agent** on your machine.

1. Ensure Docker is installed and running on your system.

2. Clone the data-analysis-agent repository:
```bash
git clone 
```

3. After cloning, navigate to the directory containing the project files.
```bash
cd data-analyst-agent
```

4. Start the application
```bash
docker compose up --build -d
```
This command sets up 4 containers: **Application**, **Python+SQL Sandbox** (DuckDB-backed), **Agent Service**, and **Frontend**. Wait for all containers to start, then access "http://localhost:3030".

> **Datasource storage:** Uploaded files (CSV, Excel, SQLite, Parquet) and the
> registry manifest live on a shared Docker volume named `datasource_data`. The
> sandbox queries them in-place through DuckDB — there is no longer a separate
> PostgreSQL container.
You can use any LLM provider’s model by setting the base_url and api_key from the settings icon in the top right (by default, Ollama is used).
- ollama (default)
- llama.cpp
- LM Studio
- vllm
- OpenAI
- Anthropic
- Groq
- (And more)

**If you don't know what is base_url and api_key, please google "(Provider Name such as llama.cpp) openai compatible"*

If you set an LLM provider such as OpenAI or Groq, your dataset schema will be sent. If you want to run everything completely locally, please proceed to the LLM setup steps below.


### LLM Setup
5. Install ollama (Skip if you already installed)
https://ollama.com/

6. Download model (Lightning-4b)


Lightning-4b is lightweight model specially trained to use in data-analysis-agent. This model offers greater stability than models with 50 times more parameters in common analytical tasks.
[Detail of Lightning 4b training and performance](https://data-analysis-agent.com/lightning-4b)


- Laptop (ex. mac book air 16GB) - 4bit Quantization + 10240 Context Window
```
ollama pull hf.co/data-analysis-agent/Lightning-4b-GGUF-short-ctx:Q4_K_M
```
- Gaming Laptop - 4bit Quantization + 40960 Context Window
```
ollama pull hf.co/data-analysis-agent/Lightning-4b-GGUF:Q4_K_M
```
- Powerful PC with GPU - No Quantization + 40960 Context Window
```
ollama pull hf.co/data-analysis-agent/Lightning-4b-GGUF:F16
```


(You can use another model like qwen3-next if you have enough GPU.)

If you feel response is too slow, add "/no_think" or "Do not think." in your query and It will generate python code immediately. 

After downloading the model, hit reload button on your browser and you can choose the model in UI. If no model appeared, check ollama port is 11434. If not, modify port of base_url from the settings icon in the top right.



### Sample Dataset & Query
For those who don’t have data on hand to analyze, we’ve prepared a sample dataset to try out **data-analysis-agent**. Please download the CSV file from this link below and upload it using the **“new tables”** button.
[employee-attrition-dataset](https://data-analysis-agent.com/sample_dataset)

Sample queries:
1. Create a **scatter plot** of **Age** versus **Total Working Years**.
2. Use a **Chi-square test** to examine whether there is a difference in **business travel frequency** between **single and married employees**.
3. Visualize the relationship between **Performance Rating** and **Number of Training Sessions attended last year**.
4. Use a **boxplot** to show the relationship between **Attrition** and **Monthly Income**, and check whether employees who left tend to have lower monthly income.
5. Analyze the correlation between **Relationship Satisfaction with Manager** and **Years with Current Manager**.
6. Perform a **t-test** to test whether there is a difference in **Job Satisfaction** between employees who have worked at **one or more previous companies** and those who have worked at **none**.

### Supported datasource types
The following datasource types can be registered through the web UI or via
the `/api/datasources/*` endpoints. They are queried in-place — files stay on
disk and remote databases are attached, never copied:

- **Files**: CSV, Excel (.xlsx / .xls — one view per sheet), SQLite (`.db` / `.sqlite`), Parquet
- **Databases**: PostgreSQL, MySQL, DuckDB

Each datasource is exposed in the sandbox as one or more DuckDB views, so the
SQL agent (and any Python code) can query CSVs, Excel sheets, and a live
Postgres database in the same query without prior ETL.

### Connect to an external database
Use the new datasource endpoint with a structured payload:

```bash
curl -X POST http://localhost:8073/api/datasources/connect \
  -H "Content-Type: application/json" \
  -d '{
    "name": "analytics_pg",
    "type": "postgres",
    "host": "your-host",
    "port": 5432,
    "database": "analytics",
    "user": "readonly_user",
    "password": "secret"
  }'
```

Or via a connection string:

```bash
curl -X POST http://localhost:8073/api/datasources/connect \
  -H "Content-Type: application/json" \
  -d '{
    "name": "analytics_pg",
    "type": "postgres",
    "connection_string": "postgresql://user:pass@host:5432/db"
  }'
```

Read-only credentials are still recommended — DuckDB attaches the database in
`READ_ONLY` mode by default for Postgres and MySQL.

## Contribution
 If you find bugs or have ideas, please share them in via GitHub Issues. For more information on contributing to data-analysis-agent you can read the [CONTRIBUTING.md](CONTRIBUTING.md) file to learn more about data-analysis-agent and how you can contribute to it.
