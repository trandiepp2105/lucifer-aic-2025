import JSZip from 'jszip';

/**
 * Formats filename based on template and values
 * @param {string} template - Template string with placeholders like "query-{query_index}-{type}"
 * @param {Object} values - Object with values to replace placeholders
 * @returns {string} Formatted filename
 */
const formatFilename = (template, values) => {
  if (!template || typeof template !== 'string') {
    return 'query-{query_index}-{type}'; // fallback to default
  }
  
  let result = template;
  Object.keys(values).forEach(key => {
    const placeholder = `{${key}}`;
    result = result.replace(new RegExp(placeholder, 'g'), values[key]);
  });
  
  return result;
};

/**
 * Converts team answers to CSV format and creates a zip file for download
 * @param {Array} teamAnswers - Array of team answer objects
 * @param {string} round - Current round ('prelims' or 'final')
 * @param {string} filenameFormat - Custom filename format template (e.g., "query-{query_index}-{type}")
 * @returns {Promise<void>}
 */
export const exportTeamAnswersToZip = async (teamAnswers, round = 'prelims', filenameFormat = 'query-{query_index}-{type}') => {
  if (!teamAnswers || teamAnswers.length === 0) {
    throw new Error('No team answers to export');
  }

  // Group team answers by query_index (skip query index 0)
  const groupedByQueryIndex = teamAnswers.reduce((acc, answer) => {
    const queryIndex = answer.query_index;
    // Skip query index 0 for team answers
    if (queryIndex === 0) {
      return acc;
    }
    if (!acc[queryIndex]) {
      acc[queryIndex] = [];
    }
    acc[queryIndex].push(answer);
    return acc;
  }, {});

  const zip = new JSZip();

  // Process each query index group
  for (const [queryIndex, answers] of Object.entries(groupedByQueryIndex)) {
    // Determine type based on first answer's qa field
    const firstAnswer = answers[0];
    const type = (firstAnswer.qa && firstAnswer.qa.trim() !== '') ? 'qa' : 'kis';
    
    // Create CSV content (no header)
    let csvContent = '';
    
    // Data rows only
    answers.forEach(answer => {
      const videoName = answer.video_name || '';
      const frameNumber = answer.frame_index || 0;
      
      if (type === 'qa') {
        const answerText = (answer.qa || '').replace(/"/g, '""'); // Escape quotes for CSV
        csvContent += `"${videoName}",${frameNumber},"${answerText}"\n`;
      } else {
        csvContent += `"${videoName}",${frameNumber}\n`;
      }
    });
    
    // Add CSV file to zip
    const fileName = formatFilename(filenameFormat, {
      query_index: queryIndex,
      type: type
    }) + '.csv';
    zip.file(fileName, csvContent);
  }

  // Generate zip file and trigger download
  try {
    const content = await zip.generateAsync({type: 'blob'});
    
    // Create download link
    const url = window.URL.createObjectURL(content);
    const link = document.createElement('a');
    link.href = url;
    link.download = `answers-${round}.zip`;
    
    // Trigger download
    document.body.appendChild(link);
    link.click();
    
    // Cleanup
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    
  } catch (error) {
    throw new Error(`Failed to generate zip file: ${error.message}`);
  }
};

/**
 * Converts answers to CSV format and creates a zip file for download
 * @param {Array} answers - Array of answer objects  
 * @param {string} round - Current round ('prelims' or 'final')
 * @param {string} filenameFormat - Custom filename format template (e.g., "query-{query_index}-{type}")
 * @returns {Promise<void>}
 */
export const exportAnswersToZip = async (answers, round = 'prelims', filenameFormat = 'query-{query_index}-{type}') => {
  if (!answers || answers.length === 0) {
    throw new Error('No answers to export');
  }

  // Group answers by query_index
  const groupedByQueryIndex = answers.reduce((acc, answer) => {
    const queryIndex = answer.query_index;
    if (!acc[queryIndex]) {
      acc[queryIndex] = [];
    }
    acc[queryIndex].push(answer);
    return acc;
  }, {});

  const zip = new JSZip();

  // Process each query index group
  for (const [queryIndex, answerList] of Object.entries(groupedByQueryIndex)) {
    // Determine type based on first answer's qa field
    const firstAnswer = answerList[0];
    const type = (firstAnswer.qa && firstAnswer.qa.trim() !== '') ? 'qa' : 'kis';
    
    // Create CSV content (no header)
    let csvContent = '';
    
    // Data rows only
    answerList.forEach(answer => {
      const videoName = answer.video_name || '';
      const frameNumber = answer.frame_index || 0;
      
      if (type === 'qa') {
        const answerText = (answer.qa || '').replace(/"/g, '""'); // Escape quotes for CSV
        csvContent += `"${videoName}",${frameNumber},"${answerText}"\n`;
      } else {
        csvContent += `"${videoName}",${frameNumber}\n`;
      }
    });
    
    // Add CSV file to zip
    const fileName = formatFilename(filenameFormat, {
      query_index: queryIndex,
      type: type
    }) + '.csv';
    zip.file(fileName, csvContent);
  }

  // Generate zip file and trigger download
  try {
    const content = await zip.generateAsync({type: 'blob'});
    
    // Create download link
    const url = window.URL.createObjectURL(content);
    const link = document.createElement('a');
    link.href = url;
    link.download = `final-answers-${round}.zip`;
    
    // Trigger download
    document.body.appendChild(link);
    link.click();
    
    // Cleanup
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    
  } catch (error) {
    throw new Error(`Failed to generate zip file: ${error.message}`);
  }
};
