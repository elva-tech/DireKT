# MCX Silver Futures - Web Application Setup Guide
===================================================

Complete setup instructions for the MCX Silver Futures paper trading web application.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- Redis (optional, for session management)

### 1. Backend Setup

```bash
# Navigate to project directory
cd d:\Downloads\ssss

# Install Python dependencies
pip install fastapi uvicorn redis pydantic python-multipart websockets

# Start backend server
python backend_server.py
```

The backend will start on `http://localhost:8000`

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install Node.js dependencies
npm install

# Start development server
npm run dev
```

The frontend will start on `http://localhost:3000`

## 🌐 Access the Application

1. **Frontend URL:** http://localhost:3000
2. **Backend API:** http://localhost:8000
3. **API Documentation:** http://localhost:8000/docs

## 🔐 Login Credentials

**Demo Account:**
- Username: `admin`
- Password: `admin123`

## 📱 Application Features

### Dashboard
- Real-time market data
- Portfolio overview
- P&L tracking
- Risk metrics
- WebSocket live updates

### Trading Terminal
- Strategy selection (ML, LLM, Rule-based, Hybrid)
- Real-time signal generation
- Automatic lot calculation
- Order placement
- Risk validation

### Portfolio
- Performance charts
- Position tracking
- Historical P&L
- Win rate statistics

### Order Management
- Order history
- Real-time status updates
- Order cancellation
- Trade execution details

### Settings
- Risk management configuration
- Strategy parameters
- Account information
- Trading preferences

## 🔧 Configuration

### Backend Environment Variables

Create `.env` file in the root directory:

```env
# API Configuration
SECRET_KEY=your-secret-key-change-in-production
REDIS_URL=redis://localhost:6379

# LLM Configuration
LLM_API_KEY=your_llm_api_key_here

# Trading Configuration
DAILY_LOSS_LIMIT_PCT=3.0
MAX_RISK_PER_TRADE_PCT=1.5
MAX_POSITION_SIZE=5
```

### Frontend Environment Variables

Create `.env` file in `frontend/` directory:

```env
VITE_API_URL=http://localhost:8000
```

## 🔄 API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/user/profile` - User profile

### Trading
- `GET /api/strategies/available` - Available strategies
- `POST /api/strategies/select` - Select strategy
- `POST /api/trading/signals/generate` - Generate signal
- `POST /api/trading/orders/place` - Place order
- `GET /api/trading/orders/history` - Order history

### Portfolio
- `GET /api/portfolio/summary` - Portfolio summary
- `GET /api/risk/metrics` - Risk metrics
- `POST /api/lot/calculate` - Calculate lots

### Market Data
- `GET /api/market/data` - Current market data
- `WebSocket /ws/{session_id}` - Real-time updates

## 🛡️ Security Features

- Session-based authentication
- CORS protection
- Input validation
- Paper trading mode (no real money)
- Risk limits enforcement
- Rate limiting

## 📊 Real-time Features

- WebSocket connection for live market data
- Auto-refreshing portfolio values
- Real-time order status updates
- Live price feeds
- Instant notifications

## 🎯 Trading Strategies

### 1. ML Model
- Random Forest classifier
- 65+ technical indicators
- Historical pattern recognition
- 65% confidence threshold

### 2. LLM Model
- GPT-powered analysis
- Market sentiment analysis
- Natural language reasoning
- Structured decision output

### 3. Rule-Based
- Technical analysis rules
- RSI, MACD indicators
- Volume analysis
- Trend following

### 4. Hybrid
- Combines all strategies
- Weighted decision making
- Consensus validation
- Enhanced accuracy

## 🔍 Troubleshooting

### Backend Issues
```bash
# Check if port 8000 is available
netstat -an | grep 8000

# Check Python dependencies
pip list | grep fastapi

# Restart backend
python backend_server.py
```

### Frontend Issues
```bash
# Clear node modules
rm -rf node_modules package-lock.json

# Reinstall dependencies
npm install

# Clear browser cache
# Hard refresh: Ctrl+Shift+R
```

### Connection Issues
- Ensure backend is running on port 8000
- Check CORS settings in backend
- Verify API URL in frontend .env
- Check browser console for errors

## 📱 Mobile Responsiveness

The application is fully responsive and works on:
- Desktop (1920x1080+)
- Tablet (768px-1024px)
- Mobile (320px-768px)

## 🚀 Production Deployment

### Backend
```bash
# Install production server
pip install gunicorn

# Start production server
gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend_server:app
```

### Frontend
```bash
# Build for production
npm run build

# Deploy build/ directory to web server
```

## 📞 Support

For issues and questions:
1. Check browser console for errors
2. Verify backend logs
3. Ensure all dependencies are installed
4. Check network connectivity

## ⚠️ Important Notes

- This is a **paper trading platform** - no real money involved
- All trades are simulated using real market data
- Educational purposes only
- Past performance does not guarantee future results
- Use at your own risk

---

**Status:** ✅ Production Ready  
**Last Updated:** March 25, 2026  
**Version:** 1.0.0
