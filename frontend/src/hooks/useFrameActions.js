import { useState } from 'react';
import { useApp } from '../contexts/AppContext';
import { useToast } from '../components/Toast/ToastProvider';
import { useSubmission } from './useSubmission';
import { TeamAnswerService } from '../services/TeamAnswerService';

/**
 * Custom hook to handle frame actions (send and submit)
 * This hook provides common logic for sending frames and handling submissions
 * that can be reused across components like DisplayListFrame and VideoPlayer
 */
export const useFrameActions = (queryMode = 'kis', allTeamAnswers = []) => {
  const [isTeamAnswerModalOpen, setIsTeamAnswerModalOpen] = useState(false);
  const [frameToSubmit, setFrameToSubmit] = useState(null);
  
  const { round, queryIndex, validateQueryModeConsistency } = useApp();
  const toast = useToast();

  // Use submission hook for submission logic
  const {
    submissionModal,
    openSubmissionModal,
    closeSubmissionModal,
    handleSubmissionConfirm,
    submitKISAnswer,
    submitQAAnswer,
    submitTRAKEAnswer
  } = useSubmission();

  const handleSendFrame = async (frame) => {
    const frameId = `${frame.video_name}-${frame.frame_index}`;
    
    // If queryMode is 'qa', open TeamAnswerModal for QA input
    if (queryMode === 'qa') {
      setFrameToSubmit(frame);
      setIsTeamAnswerModalOpen(true);
      return;
    }
    
    // Validate queryMode consistency before sending
    const validation = validateQueryModeConsistency(allTeamAnswers, queryIndex, round, 'kis');
    if (!validation.valid) {
      const modeText = validation.existingMode === 'qa' ? 'Q&A' : 'KIS';
      toast.error(`Query index ${queryIndex} already has ${modeText} answers. Cannot create KIS answer.`, 2000);
      return;
    }
    
    // For 'kis' mode, send directly without QA text
    try {
      // Prepare team answer data
      const teamAnswerData = {
        video_name: frame.video_name,
        frame_index: frame.frame_index,
        url: frame.url,
        round: round,
        query_index: queryIndex // Use queryIndex directly from AppContext
      };

      // Call API to create team answer
      const result = await TeamAnswerService.createTeamAnswer(teamAnswerData);
      
      if (result.success) {
        toast.success('Frame sent successfully!', 500);
      } else {
        // Handle different error types
        if (result.error && result.error.includes('already exists')) {
          toast.warning('This frame has already been sent for this query', 3000);
        } else {
          toast.error(result.error || 'Failed to send frame', 4000);
        }
      }
    } catch (error) {
      console.error('Error sending frame:', error);
      toast.error('An error occurred while sending frame', 4000);
    }
  };

  const handleSubmitFrame = (frame) => {
    // Determine submission type based on queryMode
    if (queryMode === 'kis') {
      submitKISAnswer(frame);
    } else if (queryMode === 'qa') {
      // For QA, we might need to get QA text from TeamAnswerModal first
      // Or directly prompt for QA text in submission modal
      submitQAAnswer(frame, ''); // TODO: Get QA text from user input
    } else if (queryMode === 'tra') {
      // This shouldn't happen for single frame, but handle gracefully
      submitKISAnswer(frame);
    } else {
      // Default to KIS
      submitKISAnswer(frame);
    }
  };

  const handleTeamAnswerModalClose = () => {
    setIsTeamAnswerModalOpen(false);
    setFrameToSubmit(null);
  };

  const handleTeamAnswerComplete = async (qaData) => {
    if (!frameToSubmit) return;
    
    // Validate queryMode consistency before proceeding
    const qaValidation = validateQueryModeConsistency(allTeamAnswers, queryIndex, round, 'qa');
    if (!qaValidation.valid) {
      const modeText = qaValidation.existingMode === 'qa' ? 'Q&A' : 'KIS';
      toast.error(`Query index ${queryIndex} already has ${modeText} answers. Cannot create Q&A answer.`, 2000);
      return;
    }
    
    try {
      // Prepare team answer data with QA text
      const teamAnswerData = {
        video_name: frameToSubmit.video_name,
        frame_index: frameToSubmit.frame_index,
        url: frameToSubmit.url,
        round: round,
        query_index: queryIndex,
        qa: qaData.qaText // Add QA text from modal
      };

      // Call API to create team answer
      const result = await TeamAnswerService.createTeamAnswer(teamAnswerData);
      
      if (result.success) {
        toast.success('Frame sent successfully!', 500);
        handleTeamAnswerModalClose();
      } else {
        // Handle different error types
        if (result.error && result.error.includes('already exists')) {
          toast.warning('This frame has already been sent for this query', 3000);
        } else {
          toast.error(result.error || 'Failed to send frame', 4000);
        }
      }
    } catch (error) {
      console.error('Error sending frame with QA:', error);
      toast.error('An error occurred while sending frame', 4000);
    }
  };

  return {
    // Submission modal state (from useSubmission hook)
    submissionModal,
    openSubmissionModal,
    closeSubmissionModal,
    handleSubmissionConfirm,
    
    // Team answer modal state
    isTeamAnswerModalOpen,
    frameToSubmit,
    
    // Actions
    handleSendFrame,
    handleSubmitFrame,
    handleTeamAnswerModalClose,
    handleTeamAnswerComplete,
    
    // Submission actions
    submitKISAnswer,
    submitQAAnswer,
    submitTRAKEAnswer
  };
};
