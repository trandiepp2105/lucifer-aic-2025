import JSZip from 'jszip';
import { saveAs } from 'file-saver';
import { apiConfig } from '../services/apiConfig';

/**
 * Export team answers and TRAKE answers to files
 */
export class ExportTeamAnswerUtils {
  
  /**
   * Export all team answers and TRAKE answers
   * @param {string} fileNameFormat - Format for filenames with placeholders {query_index} and {type}
   */
  static async exportAllAnswers(fileNameFormat = "query-p1-{query_index}-{type}") {
    try {
      // Fetch both team answers and TRAKE answers in parallel
      const [teamAnswers, trakeData] = await Promise.all([
        this.fetchTeamAnswers(),
        this.fetchTRAKEAnswers()
      ]);

      const files = [];

      // Process team answers (qa/kis types)
      if (Array.isArray(teamAnswers) && teamAnswers.length > 0) {
        const teamFiles = this.createTeamAnswerFiles(teamAnswers, fileNameFormat);
        files.push(...teamFiles);
      }

      // Process TRAKE answers (trake type) - using original format
      if (trakeData && Array.isArray(trakeData.data)) {
        const trakeFiles = this.createTRAKEAnswerFiles(trakeData.data, fileNameFormat);
        files.push(...trakeFiles);
      }
      
      // Create and download ZIP
      await this.downloadAsZip(files);
      
      return { success: true, message: `Exported ${files.length} query files` };
    } catch (error) {
      console.error('Error exporting answers:', error);
      throw new Error(`Export failed: ${error.message}`);
    }
  }

  /**
   * Fetch all team answers
   */
  static async fetchTeamAnswers() {
    const response = await fetch(`${apiConfig.baseURL}/team-answers/`);
    if (!response.ok) {
      throw new Error(`Failed to fetch team answers: ${response.status}`);
    }
    const result = await response.json();
    return result.data; // Extract data array from response
  }

  /**
   * Fetch all TRAKE answers
   */
  static async fetchTRAKEAnswers() {
    const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/`);
    if (!response.ok) {
      throw new Error(`Failed to fetch TRAKE answers: ${response.status}`);
    }
    return await response.json(); // Return original format
  }

  /**
   * Create CSV files from team answers (qa/kis types)
   * @param {Array} teamAnswers - Array of team answers
   * @param {string} fileNameFormat - Format for filenames with placeholders {query_index} and {type}
   */
  static createTeamAnswerFiles(teamAnswers, fileNameFormat) {
    const files = [];
    
    // Group by query_index
    const groupedByQuery = {};
    teamAnswers.forEach(item => {
      const queryIndex = item.query_index || 0;
      if (!groupedByQuery[queryIndex]) {
        groupedByQuery[queryIndex] = [];
      }
      groupedByQuery[queryIndex].push(item);
    });

    // Create CSV file for each query_index
    Object.keys(groupedByQuery)
      .sort((a, b) => parseInt(a) - parseInt(b))
      .forEach(queryIndex => {
        const items = groupedByQuery[queryIndex];
        if (items.length === 0) return;

        // Determine type from first item
        const firstItem = items[0];
        const type = firstItem.qa ? 'qa' : 'kis';
        
        // Generate filename using the format template
        const filename = fileNameFormat
          .replace('{query_index}', queryIndex)
          .replace('{type}', type) + '.csv';
        
        let content = '';
        if (type === 'kis') {
          content = items
            .map(item => `${item.video_name},${item.frame_index}`)
            .join('\r\n');
        } else if (type === 'qa') {
          content = items
            .map(item => `${item.video_name},${item.frame_index},"${item.qa}"`)
            .join('\r\n');
        }

        files.push({ filename, content });
      });

    return files;
  }

  /**
   * Create CSV files from TRAKE answers (trake type)
   * @param {Array} trakeData - Array of TRAKE data
   * @param {string} fileNameFormat - Format for filenames with placeholders {query_index} and {type}
   */
  static createTRAKEAnswerFiles(trakeData, fileNameFormat) {
    const files = [];
    
    // trakeData is array of {query_index, data: [groups]}
    trakeData.forEach(queryData => {
      const queryIndex = queryData.query_index;
      const groups = queryData.data;
      
      if (!groups || groups.length === 0) return;

      // Generate filename using the format template
      const filename = fileNameFormat
        .replace('{query_index}', queryIndex)
        .replace('{type}', 'trake') + '.csv';
      
      // Sort groups by group number
      const sortedGroups = [...groups].sort((a, b) => b.group - a.group);
      
      const content = sortedGroups.map(group => {
        // Sort items by frame_index within each group
        const sortedItems = [...group.items].sort((a, b) => a.frame_index - b.frame_index);
        
        // Get video_name from first item (all items in group have same video_name)
        const videoName = sortedItems[0].video_name;
        const frameIndexes = sortedItems.map(item => item.frame_index);
        
        return `${videoName},${frameIndexes.join(',')}`;
      }).join('\r\n');

      files.push({ filename, content });
    });

    return files;
  }

  /**
   * Create and download ZIP file with submission folder structure
   */
  static async downloadAsZip(files) {
    const zip = new JSZip();

    // Create submission folder
    const submissionFolder = zip.folder('submission');

    // Add CSV files to submission folder
    files.forEach(file => {
      submissionFolder.file(file.filename, file.content);
    });

    // Generate ZIP blob
    const blob = await zip.generateAsync({ type: 'blob' });
    
    // Download with team name and round
    const filename = `team_lucifer_round3.zip`;
    saveAs(blob, filename);
  }
}
