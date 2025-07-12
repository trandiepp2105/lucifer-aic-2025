import React, { useState, useCallback, useEffect, useRef } from 'react';
import ActivityBar from '../../components/ActivityBar/ActivityBar';
import Sidebar from '../../components/Sidebar/Sidebar';
import HistoryPanel from '../../components/HistoryPanel/HistoryPanel';
import DisplayListFrame from '../../components/DisplayListFrame/DisplayListFrame';
// import NeighboringFrames from '../../components/NeighboringFrames/NeighboringFrames';
import TeamAnswer from '../../components/TeamAnswer/TeamAnswer';
import Answer from '../../components/Answer/Answer';
import VideoPlayer from '../../components/VideoPlayer/VideoPlayer';
import SubmissionModal from '../../components/SubmissionModal/SubmissionModal';
import { useApp } from '../../contexts/AppContext';
import { useToast } from '../../components/Toast/ToastProvider';
import { TeamAnswerService, AnswerService } from '../../services';
import './HomePage.scss';

const HomePage = () => {
  const {
    session,
    queryMode,
    round,
    viewMode,
    stage,
    section,
    setSession,
    setQueryMode,
    setRound,
    setViewMode,
    setStage,
    setSection,
  } = useApp();

  const toast = useToast();

  const [showNeighboringFrames, setShowNeighboringFrames] = useState(false); // Mặc định ẩn
  const [showTeamAnswer, setShowTeamAnswer] = useState(true); // Show team answer panel by default
  const [frames, setFrames] = useState([]); // Add frames state
  const [availableStages, setAvailableStages] = useState(1); // Add available stages state
  const [sendingFrames, setSendingFrames] = useState(new Set()); // Track sending frames
  
  // Centralized data management for TeamAnswer and Answer
  const [allTeamAnswers, setAllTeamAnswers] = useState([]);
  const [allAnswers, setAllAnswers] = useState([]);
  const [isLoadingTeamAnswers, setIsLoadingTeamAnswers] = useState(false);
  const [isLoadingAnswers, setIsLoadingAnswers] = useState(false);
  
  // Local state for UI components (not managed by AppContext)
  const [selectedFrame, setSelectedFrame] = useState(null);
  const [isVideoPlayerOpen, setIsVideoPlayerOpen] = useState(false);
  const [isSubmissionModalOpen, setIsSubmissionModalOpen] = useState(false);
  const [frameToSubmit, setFrameToSubmit] = useState(null);
  
  // Ref to store the loadQueries function from Sidebar
  const loadQueriesRef = useRef(null);

  // Register callback for viewMode changes
  const isInitialMount = useRef(true);
  
  useEffect(() => {
    // Skip the initial mount to avoid unnecessary reload
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    
    if (loadQueriesRef.current) {
      loadQueriesRef.current();
    }
  }, [viewMode]);

  // Function to register loadQueries from Sidebar
  const registerLoadQueries = useCallback((loadQueriesFunction) => {
    loadQueriesRef.current = loadQueriesFunction;
  }, []);

  const handleSessionChange = useCallback((sessionId) => {
    setSession(sessionId);
  }, [setSession]);

  const handleFrameSelect = (frame) => {
    // Chỉ cập nhật selectedFrame, không ảnh hưởng đến showNeighboringFrames
    setSelectedFrame(frame);
  };

  const handleFrameDoubleClick = (frame) => {
    // Set the frame as selected and open VideoPlayer
    setSelectedFrame(frame);
    setIsVideoPlayerOpen(true);
  };

  const handleStageChange = useCallback((stage) => {
    setStage(stage);
  }, [setStage]);

  const handleViewModeChange = useCallback((mode) => {
    setViewMode(mode);
    // The useEffect will handle the reload when viewMode changes
  }, [setViewMode]);

  const handleAvailableStagesChange = useCallback((availableStages) => {
    setAvailableStages(availableStages);
  }, []);

  const handleFramesUpdate = useCallback((newFrames) => {
    setFrames(newFrames || []);
  }, []);

  // Centralized data fetching for TeamAnswer and Answer
  const fetchAllTeamAnswers = useCallback(async () => {
    setIsLoadingTeamAnswers(true);
    try {
      const response = await TeamAnswerService.getTeamAnswers();
      if (response.success) {
        setAllTeamAnswers(response.data.data || []);
      } else {
        console.error('Failed to fetch team answers:', response.error);
        toast.error('Failed to load team answers', 500);
        setAllTeamAnswers([]);
      }
    } catch (error) {
      console.error('Error fetching team answers:', error);
      toast.error('Error loading team answers', 500);
      setAllTeamAnswers([]);
    } finally {
      setIsLoadingTeamAnswers(false);
    }
  }, [toast]);

  const fetchAllAnswers = useCallback(async () => {
    setIsLoadingAnswers(true);
    try {
      const response = await AnswerService.getAnswers();
      if (response.success) {
        setAllAnswers(response.data || []);
      } else {
        console.error('Failed to fetch answers:', response.error);
        toast.error('Failed to load answers', 500);
        setAllAnswers([]);
      }
    } catch (error) {
      console.error('Error fetching answers:', error);
      toast.error('Error loading answers', 500);
      setAllAnswers([]);
    } finally {
      setIsLoadingAnswers(false);
    }
  }, [toast]);

  // Get unique query indexes from data
  const getUniqueQueryIndexes = useCallback((data) => {
    const queryIndexes = [...new Set(data.map(item => item.query_index))];
    return queryIndexes.sort((a, b) => a - b);
  }, []);

  const handleRoundChange = useCallback((round) => {
    setRound(round);
    // TODO: Add logic to handle round change (e.g., update API endpoints, reload data)
  }, [setRound]);

  const handleQueryModeChange = useCallback((mode) => {
    setQueryMode(mode);
    // TODO: Add logic to handle query mode change (e.g., switch between KIS and Q&A interfaces)
  }, [setQueryMode]);

  const handleSectionChange = (sectionId) => {
    setSection(sectionId);
    
    // Fetch data when switching to relevant sections
    if (sectionId === 'team-answer' && allTeamAnswers.length === 0 && !isLoadingTeamAnswers) {
      fetchAllTeamAnswers();
    } else if (sectionId === 'answer' && allAnswers.length === 0 && !isLoadingAnswers) {
      fetchAllAnswers();
    }
  };

  const toggleNeighboringFrames = () => {
    setShowNeighboringFrames(!showNeighboringFrames);
  };

  const toggleTeamAnswer = () => {
    setShowTeamAnswer(!showTeamAnswer);
  };

  const handleSubmitFrame = (frame) => {
    setFrameToSubmit(frame);
    setIsSubmissionModalOpen(true);
  };

  const handleSendFrame = async (frame) => {
    const frameId = `${frame.video_name}-${frame.frame_index}`;
    
    // Check if already sending
    if (sendingFrames.has(frameId)) {
      return;
    }

    try {
      // Add frame to sending set
      setSendingFrames(prev => new Set(prev).add(frameId));

      // Prepare team answer data
      const teamAnswerData = {
        video_name: frame.video_name,
        frame_index: frame.frame_index,
        url: frame.url,
        query_index: round === 'final' ? 0 : (stage || 1), // Use 0 for final round, otherwise use current stage
        round: round || 'prelims', // Use current round
        qa: '' // Can be extended later if needed
      };

      // Call the API
      const response = await TeamAnswerService.createTeamAnswer(teamAnswerData);

      if (response.success) {
        toast.success('Frame sent successfully!', 500);
      } else {
        toast.error(response.error || 'Failed to send frame', 4000);
      }
    } catch (error) {
      console.error('Error sending frame:', error);
      toast.error('An error occurred while sending frame', 4000);
    } finally {
      // Remove frame from sending set
      setSendingFrames(prev => {
        const newSet = new Set(prev);
        newSet.delete(frameId);
        return newSet;
      });
    }
  };

  const handleSubmissionComplete = (submissionData) => {
    setIsSubmissionModalOpen(false);
    setFrameToSubmit(null);
    // TODO: Handle submission logic here
  };

  const closeVideoPlayer = () => {
    setIsVideoPlayerOpen(false);
  };

  const closeSubmissionModal = () => {
    setIsSubmissionModalOpen(false);
    setFrameToSubmit(null);
  };

  const renderSidePanel = () => {
    switch (section) {
      case 'chat':
        return <Sidebar 
          currentStage={stage} 
          currentViewMode={viewMode}
          onFramesUpdate={handleFramesUpdate}
          onStageChange={handleStageChange}
          onViewModeChange={handleViewModeChange}
          onAvailableStagesChange={handleAvailableStagesChange}
          onSessionChange={handleSessionChange}
          onLoadQueriesRegister={registerLoadQueries}
        />;
      case 'history':
        return <HistoryPanel />;
      case 'team-answer':
        return <Sidebar 
          mode="team-answer"
          queryIndexes={getUniqueQueryIndexes(allTeamAnswers)}
          isLoading={isLoadingTeamAnswers}
          onRefresh={fetchAllTeamAnswers}
        />;
      case 'answer':
        return <Sidebar 
          mode="answer"
          queryIndexes={getUniqueQueryIndexes(allAnswers)}
          isLoading={isLoadingAnswers}
          onRefresh={fetchAllAnswers}
        />;
      default:
        return <Sidebar 
          currentStage={stage} 
          currentViewMode={viewMode}
          onFramesUpdate={handleFramesUpdate}
          onStageChange={handleStageChange}
          onViewModeChange={handleViewModeChange}
          onAvailableStagesChange={handleAvailableStagesChange}
          onSessionChange={handleSessionChange}
          onLoadQueriesRegister={registerLoadQueries}
        />;
    }
  };

  return (
    <div className="home-page">
      <div className="home-page__main">
        <ActivityBar 
          onSectionChange={handleSectionChange}
          activeSection={section}
          onRoundChange={handleRoundChange}
          onQueryModeChange={handleQueryModeChange}
          selectedRound={round}
          selectedQueryMode={queryMode}
        />
        {renderSidePanel()}
        <DisplayListFrame 
          onFrameSelect={handleFrameSelect}
          selectedFrame={selectedFrame}
          onStageChange={handleStageChange}
          onViewModeChange={handleViewModeChange}
          frames={frames}
          currentStage={stage}
          viewMode={viewMode}
          availableStages={availableStages}
          queryMode={queryMode}
          onSend={handleSendFrame}
          sendingFrames={sendingFrames}
        />
        {/* <NeighboringFrames 
          selectedFrame={selectedFrame}
          isVisible={showNeighboringFrames}
          onToggle={toggleNeighboringFrames}
          onFrameSelect={handleFrameSelect}
          onFrameDoubleClick={handleFrameDoubleClick}
          onSubmit={handleSubmitFrame}
          onSend={handleSendFrame}
          queryMode={queryMode}
          sendingFrames={sendingFrames}
        /> */}
        {section === 'team-answer' && (
          <TeamAnswer
            selectedFrame={selectedFrame}
            isVisible={showTeamAnswer}
            onToggle={toggleTeamAnswer}
            onFrameSelect={handleFrameSelect}
            onFrameDoubleClick={handleFrameDoubleClick}
            onSubmit={handleSubmitFrame}
            allTeamAnswers={allTeamAnswers}
            setAllTeamAnswers={setAllTeamAnswers}
            onRefresh={fetchAllTeamAnswers}
          />
        )}
        {section === 'answer' && (
          <Answer
            allAnswers={allAnswers}
            setAllAnswers={setAllAnswers}
            refreshAnswers={fetchAllAnswers}
            round={round}
            isVisible={true}
          />
        )}
        {(section === 'chat' || section === 'history') && (
          <TeamAnswer
            selectedFrame={selectedFrame}
            isVisible={showTeamAnswer}
            onToggle={toggleTeamAnswer}
            onFrameSelect={handleFrameSelect}
            onFrameDoubleClick={handleFrameDoubleClick}
            onSubmit={handleSubmitFrame}
            allTeamAnswers={allTeamAnswers}
            setAllTeamAnswers={setAllTeamAnswers}
            onRefresh={fetchAllTeamAnswers}
          />
        )}
      </div>

      <VideoPlayer
        isOpen={isVideoPlayerOpen}
        onClose={closeVideoPlayer}
        currentFrame={selectedFrame}
        onFrameSelect={handleFrameSelect}
        onSubmit={handleSubmitFrame}
        onSend={handleSendFrame}
        queryMode={queryMode}
        sendingFrames={sendingFrames}
      />

      <SubmissionModal
        isOpen={isSubmissionModalOpen}
        onClose={closeSubmissionModal}
        onSubmit={handleSubmissionComplete}
        frame={frameToSubmit}
      />
    </div>
  );
};

export default HomePage;
