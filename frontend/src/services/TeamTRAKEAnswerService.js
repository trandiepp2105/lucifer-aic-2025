import { apiConfig } from './apiConfig';

class TeamTRAKEAnswerService {
  static async createTRAKEAnswer(data) {
    try {
      // For single item, wrap in items array for the bulk endpoint
      const requestData = {
        items: [data]
      };
      
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error creating TRAKE answer:', error);
      throw error;
    }
  }

  static async createBulkTRAKEAnswers(data) {
    try {
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error creating bulk TRAKE answers:', error);
      throw error;
    }
  }

  static async deleteTRAKEAnswer(id) {
    try {
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/${id}/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error deleting TRAKE answer:', error);
      throw error;
    }
  }

  static async getTRAKEAnswers() {
    try {
      // Fetch all TRAKE answers without query_index filter
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error fetching TRAKE answers:', error);
      throw error;
    }
  }

  static async deleteTRAKEAnswersByIds(ids) {
    try {
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/bulk-delete/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ids }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error deleting TRAKE answers:', error);
      throw error;
    }
  }

  static async deleteAllTRAKEAnswers(queryIndex) {
    try {
      // First, get all TRAKE answers to find items for this query
      const getTRAKEResponse = await fetch(`${apiConfig.baseURL}/team-trake-answers/`);
      
      if (!getTRAKEResponse.ok) {
        throw new Error(`Failed to fetch TRAKE answers: ${getTRAKEResponse.status}`);
      }
      
      const responseData = await getTRAKEResponse.json();
      
      // Extract the data array from the response
      const allTRAKEAnswers = responseData.data || [];
      
      // Find the data for current query index
      const currentQueryData = allTRAKEAnswers.find(queryData => 
        queryData.query_index === queryIndex
      );
      
      if (!currentQueryData || !currentQueryData.data || !Array.isArray(currentQueryData.data) || currentQueryData.data.length === 0) {
        return { success: true, message: 'No TRAKE answers to delete for this query' };
      }
      
      const traKEAnswers = currentQueryData.data;
      
      // Collect all IDs from all groups
      const allIds = [];
      traKEAnswers.forEach((group, index) => {
        if (group.items && Array.isArray(group.items)) {
          group.items.forEach((item, itemIndex) => {
            if (item.id) allIds.push(item.id);
          });
        }
      });
      
      if (allIds.length === 0) {
        return { success: true, message: 'No TRAKE answer items to delete' };
      }
      
      // Now delete all by IDs
      const requestBody = { ids: allIds };
      
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/bulk-delete/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error deleting all TRAKE answers:', error);
      throw error;
    }
  }

  static async deleteGroupTRAKEAnswers(groupNumber, queryIndex) {
    try {
      // First, get all TRAKE answers for this query to find items in the group
      const getTRAKEResponse = await fetch(`${apiConfig.baseURL}/team-trake-answers/?query_index=${queryIndex}`);
      
      if (!getTRAKEResponse.ok) {
        throw new Error(`Failed to fetch TRAKE answers: ${getTRAKEResponse.status}`);
      }
      
      const responseData = await getTRAKEResponse.json();
      
      // Extract the data array from the response
      const traKEAnswers = responseData.data || [];
      
      if (!Array.isArray(traKEAnswers) || traKEAnswers.length === 0) {
        return { success: true, message: 'No TRAKE answers found' };
      }
      
      // Find the specific group and collect its item IDs
      const targetGroup = traKEAnswers.find(group => group.group === groupNumber);
      
      if (!targetGroup || !targetGroup.items || targetGroup.items.length === 0) {
        return { success: true, message: `Group ${groupNumber} not found or empty` };
      }
      
      // Collect all IDs from the target group
      const groupIds = targetGroup.items.map(item => item.id).filter(id => id);
      
      if (groupIds.length === 0) {
        return { success: true, message: `No items found in group ${groupNumber}` };
      }
      
      // Use bulk delete to remove all items in the group
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/bulk-delete/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ids: groupIds }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error deleting group TRAKE answers:', error);
      throw error;
    }
  }

  static async updateGroupForItems(itemIds, newGroup) {
    try {
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/update-group/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          item_ids: itemIds,
          new_group: newGroup
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error updating group for items:', error);
      throw error;
    }
  }

  // SSE connection for real-time updates
  static connectToUpdates() {
    const eventSource = new EventSource(`${apiConfig.baseURL}/team-trake-answers/sse/`);
    return eventSource;
  }
}

export { TeamTRAKEAnswerService };