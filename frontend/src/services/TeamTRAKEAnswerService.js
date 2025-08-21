import { apiConfig } from './apiConfig';

class TeamTRAKEAnswerService {
  static async createTRAKEAnswers(items) {
    try {
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ items }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error creating TRAKE answers:', error);
      throw error;
    }
  }

  // Alias for bulk create - same as createTRAKEAnswers
  static async createBulk(items) {
    return this.createTRAKEAnswers(items);
  }

  static async getTRAKEAnswers(queryIndex) {
    try {
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/?query_index=${queryIndex}`, {
        method: 'GET',
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

  static async deleteTRAKEAnswersByGroup(group, queryIndex = null) {
    try {
      const body = { group };
      if (queryIndex !== null) {
        body.query_index = queryIndex;
      }

      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/group-delete/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error deleting TRAKE answers by group:', error);
      throw error;
    }
  }

  static async deleteGroupTRAKEAnswers(group) {
    try {
      const response = await fetch(`${apiConfig.baseURL}/team-trake-answers/group-delete/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ group }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
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
        body: JSON.stringify({ item_ids: itemIds, new_group: newGroup }),
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
