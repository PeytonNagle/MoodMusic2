// API service for communicating with Flask backend
// https://backend-production-6b98.up.railway.app/
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

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

export interface User {
  id: number;
  email: string;
  display_name?: string | null;
  created_at?: string | null;
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

export interface AnalysisResponse {
  success: boolean;
  analysis: {
    mood?: string | null;
    matched_criteria?: string[] | null;
  };
  error?: string | null;
}

export interface RecommendResponse {
  success: boolean;
  songs: Track[];
  analysis?: {
    mood?: string | null;
    matched_criteria?: string[] | null;
  };
  error?: string | null;
}

export interface SearchRequest {
  query: string;
  limit?: number;
  emojis?: string[];
}

export interface AnalyzeRequest {
  query: string;
  emojis?: string[];
}

export interface RecommendRequest {
  query: string;
  limit?: number;
  emojis?: string[];
  analysis?: {
    mood?: string | null;
    matched_criteria?: string[] | null;
  };
  user_id?: number;
}

export interface AuthRequest {
  email: string;
  password: string;
  display_name?: string;
}

export interface AuthResponse {
  success: boolean;
  user?: User;
  error?: string;
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
   * Run fast mood/constraint analysis
   */
  static async analyzeMood(request: AnalyzeRequest): Promise<AnalysisResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      const data: AnalysisResponse = await response.json();
      return data;
    } catch (error) {
      console.error('API analyze error:', error);
      return {
        success: false,
        analysis: {},
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  /**
   * Get song recommendations using prior analysis
   */
  static async recommendMusic(request: RecommendRequest): Promise<RecommendResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/recommend`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      const data: RecommendResponse = await response.json();
      return data;
    } catch (error) {
      console.error('API recommend error:', error);
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

    static async registerUser(request: AuthRequest): Promise<AuthResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/users/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });

      const data: AuthResponse = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `HTTP error! status: ${response.status}`);
      }
      return data;
    } catch (error) {
      console.error("API register error:", error);
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error occurred",
      };
    }
  }

  static async loginUser(request: AuthRequest): Promise<AuthResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/users/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });

      const data: AuthResponse = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `HTTP error! status: ${response.status}`);
      }
      return data;
    } catch (error) {
      console.error("API login error:", error);
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error occurred",
      };
    }
  }


  

}
