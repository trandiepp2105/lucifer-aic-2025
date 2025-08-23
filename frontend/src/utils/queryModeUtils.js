import { apiConfig } from '../services/apiConfig';

/**
 * Utility functions for query mode detection and validation
 */
export class QueryModeUtils {
  
  /**
   * Detect the actual query mode for a given query index
   * @param {number} queryIndex - The query index to check
   * @returns {Promise<string>} - The detected mode: 'kis', 'qa', 'tra', or 'unknown'
   */
  static async detectQueryMode(queryIndex) {
    try {
      console.log(`🔍 Detecting query mode for query index: ${queryIndex}`);
      
      // Fetch team answers first
      console.log(`📡 Fetching team answers for query ${queryIndex}`);
      const teamAnswers = await this.fetchTeamAnswersByQuery(queryIndex);
      console.log(`✅ Team answers fetched: ${teamAnswers.length} items`);
      
      // Fetch TRAKE answers second
      console.log(`📡 Fetching TRAKE answers for query ${queryIndex}`);
      const trakeAnswers = await this.fetchTRAKEAnswersByQuery(queryIndex);
      console.log(`✅ TRAKE answers fetched: ${trakeAnswers.length} items`);

      console.log(`📊 Data found:`, { 
        teamAnswersCount: teamAnswers.length, 
        trakeAnswersCount: trakeAnswers.length 
      });

      // If we have TRAKE answers, it's a TRAKE query
      if (trakeAnswers.length > 0) {
        console.log(`✅ Query ${queryIndex} detected as TRAKE mode`);
        return 'tra';
      }

      // If we have team answers, check the type
      if (teamAnswers.length > 0) {
        const firstItem = teamAnswers[0];
        const type = firstItem.qa ? 'qa' : 'kis';
        console.log(`✅ Query ${queryIndex} detected as ${type.toUpperCase()} mode`);
        return type;
      }

      // No data found
      console.log(`⚠️ Query ${queryIndex} has no data - unknown mode`);
      return 'unknown';
      
    } catch (error) {
      console.error(`❌ Error detecting query mode for ${queryIndex}:`, error);
      return 'unknown';
    }
  }

  /**
   * Fetch team answers for a specific query index
   * @param {number} queryIndex - The query index
   * @returns {Promise<Array>} - Array of team answers
   */
  static async fetchTeamAnswersByQuery(queryIndex) {
    try {
      const response = await fetch(`${apiConfig.baseURL}/team-answers/?query_index=${queryIndex}`);
      if (!response.ok) {
        if (response.status === 404) {
          return []; // No data found is okay
        }
        throw new Error(`Failed to fetch team answers: ${response.status}`);
      }
      
      const result = await response.json();
      return result.data || [];
    } catch (error) {
      console.error('Error fetching team answers by query:', error);
      return [];
    }
  }

  /**
   * Fetch TRAKE answers for a specific query index
   * @param {number} queryIndex - The query index
   * @returns {Promise<Array>} - Array of TRAKE answers (flattened)
   */
  static async fetchTRAKEAnswersByQuery(queryIndex) {
    console.log(`🚀 fetchTRAKEAnswersByQuery called with queryIndex: ${queryIndex}`);
    try {
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/?query_index=${queryIndex}`);
      console.log('🔍 TRAKE fetch response:', response);
      if (!response.ok) {
        if (response.status === 404) {
          return []; // No data found is okay
        }
        throw new Error(`Failed to fetch TRAKE answers: ${response.status}`);
      }
      
      const result = await response.json();
      console.log(`🔍 TRAKE response for query ${queryIndex}:`, result);
      
      // When query_index is provided, format is: {data: [{group, items}, {group, items}]}
      const allItems = [];
      if (result.data && Array.isArray(result.data)) {
        result.data.forEach(group => {
          if (group.items && Array.isArray(group.items)) {
            allItems.push(...group.items);
          }
        });
      }
      
      console.log(`🔍 Flattened TRAKE items count: ${allItems.length}`);
      return allItems;
    } catch (error) {
      console.error('Error fetching TRAKE answers by query:', error);
      return [];
    }
  }

  /**
   * Validate if a mode switch is allowed for the current query index
   * @param {string} targetMode - The mode to switch to ('kis', 'qa', 'tra')
   * @param {number} queryIndex - The current query index
   * @returns {Promise<{allowed: boolean, actualMode: string, message?: string}>}
   */
  static async validateModeSwitch(targetMode, queryIndex) {
    try {
      const actualMode = await this.detectQueryMode(queryIndex);
      
      // If no data exists, allow any mode (for new queries)
      if (actualMode === 'unknown') {
        return {
          allowed: true,
          actualMode,
          message: `No data found for query ${queryIndex} - switching to ${targetMode.toUpperCase()} mode`
        };
      }

      // Check if target mode matches actual mode
      const allowed = actualMode === targetMode;
      
      if (allowed) {
        return {
          allowed: true,
          actualMode,
          message: `Successfully switched to ${targetMode.toUpperCase()} mode`
        };
      } else {
        return {
          allowed: false,
          actualMode,
          message: `Cannot switch to ${targetMode.toUpperCase()} mode. Query ${queryIndex} contains ${actualMode.toUpperCase()} data.`
        };
      }
      
    } catch (error) {
      console.error('Error validating mode switch:', error);
      return {
        allowed: false,
        actualMode: 'unknown',
        message: 'Error validating mode switch'
      };
    }
  }

  /**
   * Get user-friendly mode names
   * @param {string} mode - The mode code
   * @returns {string} - User-friendly name
   */
  static getModeName(mode) {
    const modeNames = {
      'kis': 'KIS',
      'qa': 'QA', 
      'tra': 'TRAKE',
      'unknown': 'Unknown'
    };
    return modeNames[mode] || mode;
  }
}
