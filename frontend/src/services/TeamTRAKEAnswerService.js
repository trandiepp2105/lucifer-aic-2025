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
      console.log('🔵 createBulkTRAKEAnswers called with data:', data);
      
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      console.log('🔵 Response status:', response.status);
      console.log('🔵 Response ok:', response.ok);

      if (!response.ok) {
        const errorData = await response.json();
        console.error('🔴 Response error data:', errorData);
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log('🟢 Response success data:', result);
      return result;
    } catch (error) {
      console.error('🔴 Error creating bulk TRAKE answers:', error);
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

  static async getTRAKEAnswers(queryIndex) {
    try {
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/?query_index=${queryIndex}`);
      
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
      // First, get all TRAKE answers for this query to get their IDs
      const getTRAKEResponse = await fetch(`${apiConfig.baseURL}/team-trake-answers/?query_index=${queryIndex}`);
      
      if (!getTRAKEResponse.ok) {
        throw new Error(`Failed to fetch TRAKE answers: ${getTRAKEResponse.status}`);
      }
      
      const responseData = await getTRAKEResponse.json();
      console.log('🔍 Fetched TRAKE answers response:', responseData);
      
      // Extract the data array from the response
      const traKEAnswers = responseData.data || [];
      console.log('🔍 Extracted TRAKE answers array:', traKEAnswers);
      
      if (!Array.isArray(traKEAnswers) || traKEAnswers.length === 0) {
        return { success: true, message: 'No TRAKE answers to delete' };
      }
      
      // Collect all IDs from all groups
      const allIds = [];
      traKEAnswers.forEach((group, index) => {
        console.log(`🔍 Group ${index}:`, group);
        if (group.items && Array.isArray(group.items)) {
          group.items.forEach((item, itemIndex) => {
            console.log(`🔍 Group ${index} Item ${itemIndex}:`, item);
            if (item.id) allIds.push(item.id);
          });
        }
      });
      
      console.log('🔍 Collected IDs:', allIds);
      
      if (allIds.length === 0) {
        return { success: true, message: 'No TRAKE answer items to delete' };
      }
      
      console.log('🗑️ About to delete TRAKE answers with IDs:', allIds);
      
      // Now delete all by IDs
      const requestBody = { ids: allIds };
      console.log('🗑️ DELETE request body:', requestBody);
      
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/bulk-delete/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      console.log('🗑️ DELETE response status:', response.status);
      
      if (!response.ok) {
        const errorData = await response.json();
        console.error('🗑️ DELETE error response:', errorData);
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log('🗑️ DELETE success response:', result);
      return result;
    } catch (error) {
      console.error('Error deleting all TRAKE answers:', error);
      throw error;
    }
  }

  static async deleteGroupTRAKEAnswers(groupNumber, queryIndex) {
    try {
      console.log('🗑️ deleteGroupTRAKEAnswers called with:', { groupNumber, queryIndex });
      
      // First, get all TRAKE answers for this query to find items in the group
      console.log('🔍 Fetching TRAKE answers to find group items...');
      const getTRAKEResponse = await fetch(`${apiConfig.baseURL}/team-trake-answers/?query_index=${queryIndex}`);
      
      console.log('🔍 Fetch response status:', getTRAKEResponse.status);
      
      if (!getTRAKEResponse.ok) {
        throw new Error(`Failed to fetch TRAKE answers: ${getTRAKEResponse.status}`);
      }
      
      const responseData = await getTRAKEResponse.json();
      console.log('🔍 Fetched TRAKE answers for group delete:', responseData);
      
      // Extract the data array from the response
      const traKEAnswers = responseData.data || [];
      console.log('🔍 Extracted TRAKE answers array:', traKEAnswers);
      
      if (!Array.isArray(traKEAnswers) || traKEAnswers.length === 0) {
        console.log('ℹ️ No TRAKE answers found');
        return { success: true, message: 'No TRAKE answers found' };
      }
      
      // Find the specific group and collect its item IDs
      const targetGroup = traKEAnswers.find(group => group.group === groupNumber);
      console.log('🎯 Target group found:', targetGroup);
      
      if (!targetGroup || !targetGroup.items || targetGroup.items.length === 0) {
        console.log('ℹ️ Group not found or empty');
        return { success: true, message: `Group ${groupNumber} not found or empty` };
      }
      
      // Collect all IDs from the target group
      const groupIds = targetGroup.items.map(item => item.id).filter(id => id);
      console.log(`🔍 Collected IDs for group ${groupNumber}:`, groupIds);
      
      if (groupIds.length === 0) {
        console.log('ℹ️ No items found in group');
        return { success: true, message: `No items found in group ${groupNumber}` };
      }
      
      console.log(`🗑️ About to delete group ${groupNumber} with IDs:`, groupIds);
      
      // Use bulk delete to remove all items in the group
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/bulk-delete/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ids: groupIds }),
      });

      console.log('🗑️ Group DELETE response status:', response.status);
      console.log('🗑️ Group DELETE response ok:', response.ok);
      
      if (!response.ok) {
        const errorData = await response.json();
        console.error('🗑️ Group DELETE error response:', errorData);
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log('🗑️ Group DELETE success response:', result);
      return result;
    } catch (error) {
      console.error('🔴 Error deleting group TRAKE answers:', error);
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