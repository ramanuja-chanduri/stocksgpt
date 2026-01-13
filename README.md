# StocksGPT - Financial Analysis Assistant

A full-stack web application that provides a unified chat interface for querying both GPT-4o and Gemini 2.0 Flash simultaneously, with a focus on stock market and financial analysis. The app supports multimodal inputs (text, images, PDFs) and implements RAG-based search with financial data tools.

## Features

- 🤖 **Dual LLM Support**: Query GPT-4o and Gemini 2.0 Flash side-by-side
- 📊 **Financial Analysis**: Real-time stock data, technical indicators, and financial metrics
- 📁 **Multimodal Input**: Support for text, images (JPG, PNG, WEBP), and PDFs
- 🔍 **RAG Integration**: Vector store with semantic search for relevant context
- 💬 **Session Management**: Chat history organized by sessions
- 🚀 **Streaming Responses**: Real-time streaming via WebSocket
- 📱 **Responsive Design**: Modern UI that works on desktop and mobile

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **LangChain & LangGraph** - LLM orchestration and agent workflows
- **SQLAlchemy** - Async database ORM
- **SQLite** - Database (easily switchable to PostgreSQL)
- **FAISS** - Vector store for RAG
- **yfinance** - Stock market data
- **AWS S3 / GCP Storage** - File storage

### Frontend
- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **TailwindCSS** - Styling
- **React Markdown** - Markdown rendering
- **WebSocket** - Real-time communication

## Project Structure

```
stocksGPT/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/      # API endpoints
│   │   ├── core/            # Configuration, database, security
│   │   ├── models/          # Database models and schemas
│   │   ├── services/        # Business logic (LLM, RAG, tools, storage)
│   │   └── main.py          # FastAPI app entry point
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── services/        # API and WebSocket clients
│   │   ├── types/           # TypeScript types
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- API Keys:
  - OpenAI API key (for GPT-4o)
  - Google API key (for Gemini 2.0 Flash)
  - (Optional) Tavily API key (for web search)
  - (Optional) AWS S3 or GCP credentials (for file storage)

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies using uv:**
   ```bash
   # Install uv if you don't have it
   pip install uv
   # or on Windows: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   
   # Install dependencies
   cd backend
   uv sync
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your API keys:
   ```env
   OPENAI_API_KEY=your_openai_key
   GEMINI_API_KEY=your_gemini_key
   TAVILY_API_KEY=your_tavily_key  # Optional
   AWS_ACCESS_KEY_ID=your_aws_key  # Optional for file storage
   AWS_SECRET_ACCESS_KEY=your_aws_secret
   S3_BUCKET_NAME=your_bucket_name
   ```

5. **Run the backend:**
   ```bash
   # Using uv run (recommended)
   uv run python -m app.main
   # Or with uvicorn directly:
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   The API will be available at `http://localhost:8000`
   API docs at `http://localhost:8000/docs`

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Run the development server:**
   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:5173`

## Usage

1. **Start both backend and frontend servers**

2. **Open the application** in your browser at `http://localhost:5173`

3. **Create a new session** or select an existing one from the sidebar

4. **Choose which models to query** using the toggle buttons (GPT-4o, Gemini 2.0, or both)

5. **Ask questions** about stocks, financial analysis, or upload files for analysis

6. **View responses** side-by-side from both models

## API Endpoints

### Chat
- `POST /api/chat` - Send a message to selected LLM(s)
- `WS /api/chat/stream` - WebSocket endpoint for streaming responses

### Sessions
- `GET /api/sessions` - List all chat sessions
- `GET /api/sessions/{session_id}` - Get a specific session
- `POST /api/sessions` - Create a new session
- `DELETE /api/sessions/{session_id}` - Delete a session
- `GET /api/sessions/{session_id}/messages` - Get messages for a session

### Files
- `POST /api/files/upload` - Upload a file
- `GET /api/files/{session_id}` - Get files for a session
- `DELETE /api/files/{file_id}` - Delete a file

## Financial Tools

The application includes several financial analysis tools:

1. **Stock Quote Tool**: Get real-time stock prices, market cap, P/E ratio, etc.
   - US stocks: `AAPL`, `MSFT`, `GOOGL`
   - Indian stocks: `RELIANCE.NS` (NSE), `RELIANCE.BO` (BSE)

2. **Technical Indicators**: Calculate RSI, MACD, Moving Averages

3. **Web Search**: Real-time web search for market news and updates (requires Tavily API)

4. **Financial Metrics**: Company fundamentals, revenue, profit margins, etc.

## Configuration

### Backend Configuration

Key configuration options in `backend/app/core/config.py`:

- `GPT_MODEL`: OpenAI model to use (default: `gpt-4o`)
- `GEMINI_MODEL`: Google model to use (default: `gemini-2.0-flash-exp`)
- `MAX_FILE_SIZE`: Maximum file upload size (default: 20MB)
- `SESSION_TIMEOUT_HOURS`: Session timeout period (default: 24 hours)
- `VECTOR_STORE_PATH`: Path to store vector embeddings
- `USE_GCP`: Set to `true` to use Google Cloud Storage instead of AWS S3

### Frontend Configuration

Create `.env` file in `frontend/` directory:

```env
VITE_API_URL=http://localhost:8000
```

## Development

### Running Tests

```bash
# Backend tests (when implemented)
cd backend
uv run pytest

# Frontend tests (when implemented)
cd frontend
npm test
```

### Code Quality

```bash
# Backend
cd backend
uv run black app/
uv run flake8 app/

# Frontend
cd frontend
npm run lint
```

## Deployment

### Backend

1. Set `DEBUG=false` in production
2. Use PostgreSQL instead of SQLite for production
3. Set up proper CORS origins
4. Use environment variables for all secrets
5. Consider using Docker:

```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system -e .

# Copy application code
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend

```bash
cd frontend
npm run build
# Serve the dist/ directory with nginx or similar
```

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure you're in the correct directory and virtual environment is activated
2. **API key errors**: Verify your API keys are correctly set in `.env`
3. **Database errors**: Delete `stocksgpt.db` to reset the database
4. **CORS errors**: Check `CORS_ORIGINS` in backend config matches your frontend URL
5. **File upload errors**: Ensure storage credentials are configured if using cloud storage

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License

## Acknowledgments

- OpenAI for GPT-4o
- Google for Gemini 2.0 Flash
- LangChain team for excellent LLM orchestration tools
- yfinance for stock market data
