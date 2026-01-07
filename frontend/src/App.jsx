import React, { useState, useEffect } from 'react';
import Upload from './components/Upload';
import YouTubeClipCreator from './components/YouTubeClipCreator';
import VideoPlayer from './components/VideoPlayer';
import SubtitleEditor from './components/SubtitleEditor';
import StyleEditor from './components/StyleEditor';
import { parseVTT, stringifyVTT, stringifySRT } from './utils/vtt';

function App() {
  const [status, setStatus] = useState('idle'); // idle, uploading, success, error
  const [videoData, setVideoData] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [progressMessage, setProgressMessage] = useState('');
  const [mode, setMode] = useState('upload'); // 'upload' or 'youtube'

  // Subtitle State
  const [subtitles, setSubtitles] = useState([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [playerAspectRatio, setPlayerAspectRatio] = useState('16:9');

  // Style State
  const [styles, setStyles] = useState({
    fontSize: 24,
    color: '#ffffff',
    backgroundColor: '#00000080', // Hex with alpha
    bottom: 10,
    outlineColor: '#000000',
    outlineWidth: 0,
    fontWeight: 'normal',
  });

  // Saved Styles State
  const [savedStyles, setSavedStyles] = useState({});
  const [defaultStyleName, setDefaultStyleName] = useState('');
  const [recentStyleNames, setRecentStyleNames] = useState([]);

  // Load saved styles from localStorage on mount
  useEffect(() => {
    const loaded = localStorage.getItem('savedStyles');
    if (loaded) {
      try {
        setSavedStyles(JSON.parse(loaded));
      } catch (e) {
        console.error('Failed to parse saved styles', e);
      }
    }
    const defaultName = localStorage.getItem('defaultStyleName');
    if (defaultName) {
      setDefaultStyleName(defaultName);
    }
    const recent = localStorage.getItem('recentStyleNames');
    if (recent) {
      try {
        setRecentStyleNames(JSON.parse(recent));
      } catch (e) {
        console.error('Failed to parse recent style names', e);
      }
    }
  }, []);

  const handleSaveStyle = (name, styleObj) => {
    const newSavedStyles = { ...savedStyles, [name]: styleObj };
    setSavedStyles(newSavedStyles);
    localStorage.setItem('savedStyles', JSON.stringify(newSavedStyles));
  };

  const handleLoadStyle = (name) => {
    if (savedStyles[name]) {
      setStyles(savedStyles[name]);
      handleStyleUsed(name);
    }
  };

  const handleStyleUsed = (name) => {
    if (!name) return;
    setRecentStyleNames(prev => {
      const filtered = prev.filter(n => n !== name);
      const updated = [name, ...filtered].slice(0, 5); // Keep top 5
      localStorage.setItem('recentStyleNames', JSON.stringify(updated));
      return updated;
    });
  };

  const handleDeleteStyle = (name) => {
    const newSavedStyles = { ...savedStyles };
    delete newSavedStyles[name];
    setSavedStyles(newSavedStyles);
    localStorage.setItem('savedStyles', JSON.stringify(newSavedStyles));

    // Remove from recent history
    setRecentStyleNames(prev => {
      const updated = prev.filter(n => n !== name);
      localStorage.setItem('recentStyleNames', JSON.stringify(updated));
      return updated;
    });

    // Clear default if deleted
    if (defaultStyleName === name) {
      setDefaultStyleName('');
      localStorage.removeItem('defaultStyleName');
    }
  };

  const handleSetDefaultStyle = (name) => {
    setDefaultStyleName(name);
    if (name) {
      localStorage.setItem('defaultStyleName', name);
    } else {
      localStorage.removeItem('defaultStyleName');
    }
  };

  const handleUploadStart = () => {
    setStatus('uploading');
    setErrorMessage('');
  };

  const handleUploadSuccess = async (data) => {
    setVideoData(data);

    // subtitle_urlがnullの場合（文字起こしをスキップした場合）
    if (!data.subtitle_url) {
      setSubtitles([]);
      setStatus('success');
      setProgressMessage('字幕ファイルをアップロードしてください');
      return;
    }

    try {
      // Fetch and parse the VTT file
      const response = await fetch(`${data.subtitle_url}`);
      const vttText = await response.text();
      const parsedSubtitles = parseVTT(vttText);
      setSubtitles(parsedSubtitles);
      setStatus('success');
      setProgressMessage('');
    } catch (e) {
      console.error(e);
      setErrorMessage('字幕ファイルの読み込みに失敗しました');
      setStatus('error');
    }
  };

  const handleUploadError = (msg) => {
    setStatus('error');
    setErrorMessage(msg);
  };

  const handleDownload = async () => {
    if (!videoData) return;

    const originalStatus = status;
    setStatus('processing');
    setProgressMessage('動画を作成しています... (数分かかる場合があります)');

    try {
      const vttContent = stringifyVTT(subtitles);

      // Determine the default style: use the saved default style if set, otherwise use a clean basic style
      let defaultStyle;
      if (defaultStyleName && savedStyles[defaultStyleName]) {
        defaultStyle = savedStyles[defaultStyleName];
      } else {
        // Use a clean basic style without any prefix settings
        defaultStyle = {
          fontSize: 24,
          color: '#ffffff',
          backgroundColor: '#00000080',
          bottom: 10,
          outlineColor: '#000000',
          outlineWidth: 0,
          fontWeight: 'normal',
        };
      }

      const response = await fetch('/burn', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          video_filename: videoData.unique_filename,
          subtitle_content: vttContent,
          styles: defaultStyle,
          saved_styles: savedStyles,
          style_map: subtitles.reduce((acc, sub, index) => {
            if (sub.styleName) {
              acc[index] = sub.styleName;
            }
            return acc;
          }, {})
        }),
      });

      if (!response.ok) {
        throw new Error('動画の作成に失敗しました');
      }

      const data = await response.json();

      setProgressMessage('ダウンロードを開始します...');

      // Use the download endpoint which forces download via headers
      // data.filename is the burned filename on disk (e.g. uuid_burned.mp4)
      const downloadUrl = `/download/${data.filename}`;

      const link = document.createElement('a');
      link.href = downloadUrl;
      // download attribute is ignored if header is set, but good to have
      link.download = `captioned_${videoData.filename}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Keep the message for a moment
      setTimeout(() => {
        setStatus(originalStatus);
        setProgressMessage('');
      }, 3000);

    } catch (e) {
      console.error(e);
      alert('動画の作成に失敗しました: ' + e.message);
      setStatus(originalStatus);
      setProgressMessage('');
    }
  };

  const handleDownloadVTT = () => {
    if (subtitles.length === 0) return;

    const vttContent = stringifyVTT(subtitles);
    const blob = new Blob([vttContent], { type: 'text/vtt' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = videoData?.filename ? `${videoData.filename.replace(/\.[^/.]+$/, '')}.vtt` : 'subtitles.vtt';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleDownloadSRT = () => {
    if (subtitles.length === 0) return;

    const srtContent = stringifySRT(subtitles);
    const blob = new Blob([srtContent], { type: 'text/srt' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = videoData?.filename ? `${videoData.filename.replace(/\.[^/.]+$/, '')}.srt` : 'subtitles.srt';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const reset = () => {
    setStatus('idle');
    setVideoData(null);
    setSubtitles([]);
    setCurrentTime(0);
  };

  const handleSeek = (time) => {
    const videoElement = document.querySelector('video');
    if (videoElement) {
      videoElement.currentTime = time;
    }
  };

  const handlePause = () => {
    const videoElement = document.querySelector('video');
    if (videoElement) {
      videoElement.pause();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            動画文字起こし・字幕編集アプリ
          </h1>
          <p className="text-gray-600">
            AIで文字起こしを行い、字幕の内容やデザインを自由に編集できます
          </p>
        </div>

        <div className="flex justify-center mb-8 space-x-4">
          <button
            onClick={() => setMode('upload')}
            className={`px-4 py-2 rounded-md ${mode === 'upload' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border'}`}
          >
            ファイルアップロード
          </button>
          <button
            onClick={() => setMode('youtube')}
            className={`px-4 py-2 rounded-md ${mode === 'youtube' ? 'bg-red-600 text-white' : 'bg-white text-gray-700 border'}`}
          >
            YouTube切り抜き
          </button>
        </div>

        {mode === 'youtube' ? (
          <YouTubeClipCreator />
        ) : (
          <>
            {status === 'idle' && (
              <div className="max-w-3xl mx-auto bg-white rounded-xl shadow-sm p-8">
                <Upload
                  onUploadStart={handleUploadStart}
                  onUploadSuccess={handleUploadSuccess}
                  onUploadError={handleUploadError}
                />
              </div>
            )}

            {status === 'uploading' && (
              <div className="max-w-3xl mx-auto bg-white rounded-xl shadow-sm p-12 text-center">
                <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <h3 className="text-xl font-medium text-gray-900">処理中...</h3>
                <p className="text-gray-500 mt-2">
                  動画のアップロードと文字起こしを行っています。<br />
                  しばらくお待ちください。
                </p>
              </div>
            )}

            {(status === 'success' || status === 'processing') && videoData && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left Column: Video and Style Editor */}
                <div className="lg:col-span-2 space-y-6">
                  <div className="flex justify-end mb-2">
                    <button
                      onClick={() => setPlayerAspectRatio(playerAspectRatio === '16:9' ? '9:16' : '16:9')}
                      className="text-xs bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-1 rounded flex items-center gap-1"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                      </svg>
                      プレイヤー比率: {playerAspectRatio}
                    </button>
                  </div>
                  <VideoPlayer
                    videoUrl={videoData.video_url}
                    subtitles={subtitles}
                    styles={styles}
                    savedStyles={savedStyles}
                    defaultStyleName={defaultStyleName}
                    onTimeUpdate={setCurrentTime}
                    isVertical={playerAspectRatio === '9:16'}
                  />

                  <StyleEditor
                    styles={styles}
                    onStyleChange={setStyles}
                    savedStyles={savedStyles}
                    onSave={handleSaveStyle}
                    onLoad={handleLoadStyle}
                    onDelete={handleDeleteStyle}
                    defaultStyleName={defaultStyleName}
                    onSetDefault={handleSetDefaultStyle}
                    onStyleUsed={handleStyleUsed}
                  />

                  <div className="text-center pt-4 flex justify-center space-x-4 flex-wrap gap-y-2">
                    <button
                      onClick={reset}
                      className="px-6 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors"
                    >
                      新しい動画をアップロード
                    </button>
                    <button
                      onClick={handleDownload}
                      disabled={status === 'processing' || subtitles.length === 0}
                      className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:bg-blue-300"
                      title={subtitles.length === 0 ? '字幕ファイルをアップロードしてください' : ''}
                    >
                      {status === 'processing' ? progressMessage : '動画をダウンロード'}
                    </button>

                    {subtitles.length > 0 && (
                      <button
                        onClick={handleDownloadSRT}
                        className="px-6 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors flex items-center"
                      >
                        SRTをダウンロード
                      </button>
                    )}

                    {subtitles.length > 0 && (
                      <button
                        onClick={handleDownloadVTT}
                        className="px-6 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors flex items-center"
                      >
                        VTTをダウンロード
                      </button>
                    )}

                    {videoData?.fcpxml_url && (
                      <a
                        href={videoData.fcpxml_url}
                        download
                        className="px-6 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors flex items-center"
                      >
                        FCPXML (DaVinci)
                      </a>
                    )}
                  </div>
                </div>

                {/* Right Column: Subtitle Editor */}
                <div className="lg:col-span-1 space-y-6">
                  {!videoData.subtitle_url && subtitles.length === 0 && (
                    <div className="bg-yellow-50 border-2 border-yellow-200 rounded-lg p-6">
                      <h3 className="font-bold text-yellow-900 mb-3 text-center">
                        字幕ファイルをアップロード
                      </h3>
                      <p className="text-sm text-yellow-800 mb-4 text-center">
                        VTTまたはSRTファイルをアップロードしてください
                      </p>
                      <label className="flex items-center justify-center gap-2 px-4 py-3 bg-yellow-500 text-white rounded-lg cursor-pointer hover:bg-yellow-600 transition-colors">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        字幕ファイルを選択
                        <input
                          type="file"
                          accept=".vtt,.srt"
                          className="hidden"
                          onChange={async (e) => {
                            const file = e.target.files[0];
                            if (!file) return;

                            const formData = new FormData();
                            formData.append('file', file);
                            formData.append('video_filename', videoData.unique_filename);

                            try {
                              setProgressMessage('字幕ファイルをアップロード中...');
                              const response = await fetch('/youtube/upload-subtitle', {
                                method: 'POST',
                                body: formData
                              });

                              if (!response.ok) {
                                throw new Error('字幕アップロードに失敗しました');
                              }

                              const data = await response.json();

                              // Update videoData with new URLs
                              setVideoData({
                                ...videoData,
                                subtitle_url: data.subtitle_url,
                                srt_url: data.srt_url,
                                fcpxml_url: data.fcpxml_url
                              });

                              // Load and parse the subtitle file
                              const vttResponse = await fetch(data.subtitle_url);
                              const vttText = await vttResponse.text();
                              const parsedSubtitles = parseVTT(vttText);
                              setSubtitles(parsedSubtitles);

                              setProgressMessage('字幕ファイルがアップロードされました');
                              setTimeout(() => setProgressMessage(''), 3000);
                            } catch (error) {
                              console.error('Error uploading subtitle:', error);
                              alert(`エラー: ${error.message}`);
                              setProgressMessage('');
                            } finally {
                              e.target.value = '';
                            }
                          }}
                        />
                      </label>
                    </div>
                  )}

                  {subtitles.length > 0 && (
                    <SubtitleEditor
                      subtitles={subtitles}
                      onSubtitlesChange={setSubtitles}
                      currentTime={currentTime}
                      onTimeUpdate={setCurrentTime}
                      videoRef={null}
                      onSeek={(time) => {
                        const video = document.querySelector('video');
                        if (video) video.currentTime = time;
                      }}
                      savedStyles={savedStyles}
                      recentStyleNames={recentStyleNames}
                      onStyleUsed={handleStyleUsed}
                    />
                  )}
                </div>
              </div>
            )}

            {status === 'error' && (
              <div className="max-w-3xl mx-auto bg-white rounded-xl shadow-sm p-8 text-center">
                <div className="text-red-500 text-xl mb-4">⚠️ エラーが発生しました</div>
                <p className="text-gray-600 mb-6">{errorMessage}</p>
                <button
                  onClick={reset}
                  className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                >
                  やり直す
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default App;
