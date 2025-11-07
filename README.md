# Text-to-Spotify Fullstack Application

A fullstack application that helps users discover music through natural language descriptions using OpenAI GPT-4o-mini and Spotify's API.

## Features

- **AI-Powered Music Discovery**: Describe the music you want in natural language
- **30-Second Previews**: Play previews directly in the app using Spotify's preview URLs
- **Spotify Integration**: Open tracks directly in Spotify
- **Modern UI**: Dark theme with glass-morphism design and purple/pink gradients
- **Responsive Design**: Works on desktop and mobile devices

## Tech Stack

### Backend
- **Flask**: Python web framework
- **OpenAI API**: GPT-4o-mini for music suggestions
- **Spotipy**: Spotify Web API client
- **Python-dotenv**: Environment variable management

### Frontend
- **React**: Frontend framework
- **TypeScript**: Type safety
- **Vite**: Build tool and dev server
- **Tailwind CSS**: Styling framework
- **shadcn/ui**: Component library
- **Lucide React**: Icons

## Project Structure

```
VibeCodeLab10-15/
├── backend/
│   ├── app.py              # Flask server with API endpoints
│   ├── config.py           # Configuration for API keys
│   ├── services/
│   │   ├── openai_service.py   # OpenAI GPT-4o-mini integration
│   │   └── spotify_service.py  # Spotipy integration
│   ├── requirements.txt    # Python dependencies
│   └── .env               # Environment variables (API keys)
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx         # Main React component
│   │   ├── components/
│   │   │   ├── SearchInput.tsx    # Text input component
│   │   │   ├── ResultsGrid.tsx    # Display track results
│   │   │   ├── SongCard.tsx       # Individual track with preview player
│   │   │   ├── figma/
│   │   │   │   └── ImageWithFallback.tsx
│   │   │   └── ui/
│   │   │       ├── button.tsx
│   │   │       ├── textarea.tsx
│   │   │       └── utils.ts
│   │   └── services/
│   │       └── api.ts      # API calls to Flask backend
│   └── vite.config.ts
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.8+
- Node.js 16+
- OpenAI API key
- Spotify Developer account (Client ID and Secret)

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

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Edit the `.env` file and add your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   SPOTIPY_CLIENT_ID=your_spotify_client_id_here
   SPOTIPY_CLIENT_SECRET=your_spotify_client_secret_here
   ```

5. **Start the Flask server:**
   ```bash
   python app.py
   ```
   The backend will run on `http://localhost:5000`

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```
   The frontend will run on `http://localhost:3000`

## API Endpoints

### POST /api/search
Search for music based on text description.

**Request:**
```json
{
  "query": "upbeat indie rock for a road trip",
  "limit": 10
}
```

**Response:**
```json
{
  "success": true,
  "songs": [
    {
      "id": "spotify_track_id",
      "title": "Song Title",
      "artist": "Artist Name",
      "album": "Album Name",
      "album_art": "https://...",
      "preview_url": "https://...",
      "spotify_url": "https://...",
      "release_year": "2023",
      "duration_formatted": "3:45"
    }
  ],
  "error": null
}
```

### GET /api/health
Check API health and service connections.

## Usage

1. Open `http://localhost:3000` in your browser
2. Enter a description of the music you're looking for (e.g., "chill lo-fi beats for studying")
3. Click "Find Music" or press Enter
4. Browse the results and play 30-second previews
5. Click "Open in Spotify" to listen to full tracks

## Development Notes

- The app uses Spotify's 30-second preview URLs (no OAuth required)
- OpenAI GPT-4o-mini generates song suggestions based on text descriptions
- The backend validates and enriches suggestions with Spotify metadata
- Error handling includes graceful fallbacks for missing previews or API failures

## Troubleshooting

### Common Issues

1. **"Failed to connect to the server"**
   - Make sure the Flask backend is running on port 5000
   - Check that CORS is enabled in the Flask app

2. **"OpenAI service not configured"**
   - Verify your OpenAI API key is correct in the `.env` file
   - Check that you have credits in your OpenAI account

3. **"Spotify service not configured"**
   - Verify your Spotify Client ID and Secret are correct
   - Make sure your Spotify app is not in development mode restrictions

4. **No preview URLs**
   - Some tracks don't have preview URLs available
   - This is normal and handled gracefully by the app

### Health Check

Visit `http://localhost:5000/api/health` to check if all services are connected properly.

## Future Enhancements

- User authentication and search history
- Playlist creation and saving
- Advanced filtering options
- Music recommendation based on listening history
- Integration with Spotify Web Playback SDK for full playback control
