// API service for communicating with Flask backend
const API_BASE_URL = 'https://frontend-production-20ff.up.railway.app/

export interface Track {
  id: string | null;
  title: string;
  artist: string;
  album: string;
  album_art: string | null;
  preview_url: string | null;
  spotify_url: string | null;
  release_year: string | null;
  duration_formatted: string | null;
}

export interface SearchResponse {
  success: boolean;
  songs: Track[];
  error: string | null;
  analysis?: {
    mood?: string | null;
    matched_criteria?: string[] | null;
  };
}

export interface SearchRequest {
  query: string;
  limit?: number;
}

export class ApiService {
  /**
   * Search for music based on text description
   */
  static async searchMusic(request: SearchRequest): Promise<SearchResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data: SearchResponse = await response.json();
      return data;
    } catch (error) {
      console.error('API search error:', error);
      return {
        success: false,
        songs: [],
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  /**
   * Check if the API is healthy and services are connected
   */
  static async healthCheck(): Promise<{
    status: string;
    services: {
      openai: string;
      spotify: string;
    };
    config_loaded: boolean;
  }> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/health`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Health check error:', error);
      throw error;
    }
  }

  /**
   * Test API connection
   */
  static async testConnection(): Promise<boolean> {
    try {
      await this.healthCheck();
      return true;
    } catch {
      return false;
    }
  }
}
