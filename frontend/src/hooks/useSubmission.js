import { useState } from 'react';
import SubmissionService from '../services/SubmissionService';
import { useToast } from '../components/Toast/ToastProvider';
import { useApp } from '../contexts/AppContext';

/**
 * Custom hook for handling submissions with confirmation modal
 */
export const useSubmission = () => {
  const [submissionModal, setSubmissionModal] = useState({
    isOpen: false,
    type: null, // 'kis', 'qa', 'trake'
    frameData: null,
    qaText: '',
    isSubmitting: false
  });

  const toast = useToast();
  const { dresSession, evaluationId } = useApp();

  const openSubmissionModal = (type, frameData, qaText = '') => {
    setSubmissionModal({
      isOpen: true,
      type,
      frameData,
      qaText,
      isSubmitting: false
    });
  };

  const closeSubmissionModal = () => {
    if (!submissionModal.isSubmitting) {
      setSubmissionModal({
        isOpen: false,
        type: null,
        frameData: null,
        qaText: '',
        isSubmitting: false
      });
    }
  };

  const handleSubmissionConfirm = async (newQAText) => {
    const { type, frameData } = submissionModal;
    let qaText = submissionModal.qaText;
    if (type === 'qa' && typeof newQAText === 'string') {
      qaText = newQAText;
    }

    if (!type || !frameData) {
      toast.error('Invalid submission data');
      return;
    }

    setSubmissionModal(prev => ({ ...prev, isSubmitting: true }));

    try {
      let response;

      switch (type) {
        case 'kis':
          response = await SubmissionService.submitKISAnswer(
            frameData.video_name,
            frameData.frame_index,
            dresSession,
            evaluationId
          );
          break;

        case 'qa':
          if (!qaText.trim()) {
            toast.error('QA text is required');
            setSubmissionModal(prev => ({ ...prev, isSubmitting: false }));
            return;
          }
          response = await SubmissionService.submitQAAnswer(
            frameData.video_name,
            frameData.frame_index,
            qaText.trim(),
            dresSession,
            evaluationId
          );
          break;

        case 'trake':
          if (!Array.isArray(frameData) || frameData.length === 0) {
            toast.error('No frames to submit');
            setSubmissionModal(prev => ({ ...prev, isSubmitting: false }));
            return;
          }
          response = await SubmissionService.submitTRAKEAnswer(
            frameData,
            dresSession,
            evaluationId
          );
          break;

        default:
          toast.error('Unknown submission type');
          setSubmissionModal(prev => ({ ...prev, isSubmitting: false }));
          return;
      }

      // Handle response based on DRES format
      if (response.status === true) {
        // DRES returned successful submission
        if (response.submission === 'CORRECT') {
          toast.success(`✓ ${response.description || 'Submission correct, well done!'}`);
        } else if (response.submission === 'WRONG') {
          toast.error(`✗ ${response.description || 'Submission wrong, try again!'}`);
        } else {
          // Unknown submission status but status is true
          toast.success(`✓ ${response.description || 'Submission processed'}`);
        }
      } else if (response.status === false) {
        // DRES rejected the submission
        toast.warning(`⚠ ${response.description || 'Submission rejected'}`);
      } else {
        // Fallback for unexpected response format
        toast.error('Unexpected response format from server');
      }

      closeSubmissionModal();

    } catch (error) {
      console.error('Submission error:', error);
      
      // Handle API errors
      if (error.response?.data?.message) {
        toast.error(error.response.data.message);
      } else {
        toast.error('Failed to submit answer. Please try again.');
      }
      
      setSubmissionModal(prev => ({ ...prev, isSubmitting: false }));
    }
  };

  // Convenience methods for different submission types
  const submitKISAnswer = (frame) => {
    openSubmissionModal('kis', frame);
  };

  const submitQAAnswer = (frame, qaText) => {
    openSubmissionModal('qa', frame, qaText);
  };

  const submitTRAKEAnswer = (frameList) => {
    openSubmissionModal('trake', frameList);
  };

  return {
    submissionModal,
    openSubmissionModal,
    closeSubmissionModal,
    handleSubmissionConfirm,
    submitKISAnswer,
    submitQAAnswer,
    submitTRAKEAnswer
  };
};
