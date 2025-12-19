import React, { useRef, useEffect } from 'react';
import DanmakuLayer from './DanmakuLayer';

export default function VideoPlayer({ videoUrl, subtitles, styles, savedStyles, defaultStyleName, onTimeUpdate, comments }) {
    const videoRef = useRef(null);

    const [activeSubtitles, setActiveSubtitles] = React.useState([]);
    const [scale, setScale] = React.useState(1); // Scale factor relative to 1080p
    const [currentTime, setCurrentTime] = React.useState(0);

    const handleTimeUpdate = () => {
        if (videoRef.current) {
            const time = videoRef.current.currentTime;
            setCurrentTime(time);
            onTimeUpdate(time);

            // Find all active subtitles (filter instead of find)
            const subs = subtitles.filter(s => time >= s.start && time <= s.end);
            setActiveSubtitles(subs);
        }
    };

    // Helper function to get style for a subtitle
    const getStyleForSub = (sub) => {
        // If subtitle has explicit style, use it
        if (sub && sub.styleName && savedStyles && savedStyles[sub.styleName]) {
            return savedStyles[sub.styleName];
        }
        // If defaultStyleName is set and exists in savedStyles, use it
        if (defaultStyleName && savedStyles && savedStyles[defaultStyleName]) {
            return savedStyles[defaultStyleName];
        }
        // Otherwise use current styles
        return styles;
    };

    // Helper to check if background is transparent
    const isTransparent = (color) => {
        if (!color) return true;
        if (color.length === 9) { // #RRGGBBAA
            const alpha = parseInt(color.slice(7, 9), 16);
            return alpha === 0;
        }
        return false; // Assume opaque if #RRGGBB
    };

    // Update activeSubtitles when subtitles change (e.g. text edit or style change) while paused
    useEffect(() => {
        if (videoRef.current) {
            const time = videoRef.current.currentTime;
            const subs = subtitles.filter(sub => time >= sub.start && time <= sub.end);
            setActiveSubtitles(subs);
        }
    }, [subtitles]);

    useEffect(() => {
        if (videoRef.current) {
            videoRef.current.load();
        }
    }, [videoUrl]);

    // Update scale based on video player height (Backend uses 1080p reference)
    useEffect(() => {
        if (!videoRef.current) return;

        const updateScale = () => {
            if (videoRef.current) {
                const height = videoRef.current.clientHeight;
                // Backend uses PlayResY = 1080
                setScale(height / 1080);
            }
        };

        const observer = new ResizeObserver(updateScale);
        observer.observe(videoRef.current);

        // Initial calculation
        videoRef.current.addEventListener('loadedmetadata', updateScale);
        updateScale();

        return () => {
            observer.disconnect();
            if (videoRef.current) {
                videoRef.current.removeEventListener('loadedmetadata', updateScale);
            }
        };
    }, []);

    // Build text shadow for double outline and drop shadow
    const buildTextShadow = (subStyle) => {
        const shadows = [];

        // Inner outline (using text-shadow to create outline effect)
        const innerWidth = (subStyle.outlineWidth || 0) * scale;
        const innerColor = subStyle.outlineColor || '#000000';
        if (innerWidth > 0) {
            // Create outline using multiple shadows
            for (let angle = 0; angle < 360; angle += 45) {
                const rad = (angle * Math.PI) / 180;
                const x = Math.cos(rad) * innerWidth;
                const y = Math.sin(rad) * innerWidth;
                shadows.push(`${x}px ${y}px 0 ${innerColor}`);
            }
        }

        // Outer outline
        const outerWidth = (subStyle.outerOutlineWidth || 0) * scale;
        const outerColor = subStyle.outerOutlineColor || '#FFFFFF';
        if (outerWidth > 0) {
            const totalWidth = innerWidth + outerWidth;
            for (let angle = 0; angle < 360; angle += 45) {
                const rad = (angle * Math.PI) / 180;
                const x = Math.cos(rad) * totalWidth;
                const y = Math.sin(rad) * totalWidth;
                shadows.push(`${x}px ${y}px 0 ${outerColor}`);
            }
        }

        // Drop shadow
        const shadowBlur = (subStyle.shadowBlur || 0) * scale;
        const shadowX = (subStyle.shadowOffsetX || 0) * scale;
        const shadowY = (subStyle.shadowOffsetY || 0) * scale;
        const shadowColor = subStyle.shadowColor || '#000000';
        if (shadowBlur > 0 || shadowX !== 0 || shadowY !== 0) {
            shadows.push(`${shadowX}px ${shadowY}px ${shadowBlur}px ${shadowColor}`);
        }

        return shadows.length > 0 ? shadows.join(', ') : 'none';
    };

    const handleCaptureThumbnail = () => {
        if (!videoRef.current) return;

        const video = videoRef.current;
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Download image
        const dataUrl = canvas.toDataURL('image/png');
        const link = document.createElement('a');
        link.download = `thumbnail_${Date.now()}.png`;
        link.href = dataUrl;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    return (
        <div className="relative w-full max-w-4xl mx-auto bg-black rounded-lg overflow-hidden shadow-xl group">
            <video
                ref={videoRef}
                className="w-full aspect-video"
                controls
                crossOrigin="anonymous"
                onTimeUpdate={handleTimeUpdate}
            >
                <source src={`${videoUrl}`} type="video/mp4" />
                お使いのブラウザは動画タグをサポートしていません。
            </video>

            {/* Danmaku Overlay */}
            <DanmakuLayer
                comments={comments}
                currentTime={currentTime}
                videoHeight={videoRef.current?.clientHeight || videoRef.current?.videoHeight || 1080}
            />

            {/* Custom Subtitle Overlay - Renders ALL active subtitles */}
            {activeSubtitles.map((sub) => {
                const subStyle = getStyleForSub(sub);
                // Map alignment to CSS properties
                const alignmentStyles = {
                    'left': { textAlign: 'left', justifyContent: 'flex-start', paddingLeft: '5%' },
                    'center': { textAlign: 'center', justifyContent: 'center' },
                    'right': { textAlign: 'right', justifyContent: 'flex-end', paddingRight: '5%' },
                    'top-left': { textAlign: 'left', justifyContent: 'flex-start', paddingLeft: '5%' },
                    'top': { textAlign: 'center', justifyContent: 'center' },
                    'top-right': { textAlign: 'right', justifyContent: 'flex-end', paddingRight: '5%' },
                };
                const alignment = subStyle.alignment || 'center';
                const alignStyle = alignmentStyles[alignment] || alignmentStyles.center;
                const isTop = alignment.startsWith('top');

                return (
                    <div
                        key={sub.id}
                        className="absolute left-0 right-0 flex pointer-events-none transition-all duration-200"
                        style={{
                            ...(isTop
                                ? { top: `${100 - (subStyle.bottom || 10)}%` }
                                : { bottom: `${subStyle.bottom || 10}%` }
                            ),
                            ...alignStyle,
                        }}
                    >
                        {/* Image Prefix - placed OUTSIDE the text span */}
                        {subStyle.prefixImage && (
                            <img
                                src={subStyle.prefixImage}
                                alt="prefix"
                                style={{
                                    height: `${(subStyle.prefixImageSize || 32) * scale}px`,
                                    width: 'auto',
                                    display: 'inline-block',
                                    marginRight: `${10 * scale}px`, // 10px spacing
                                    alignSelf: 'center',
                                }}
                            />
                        )}
                        <span
                            style={{
                                fontFamily: subStyle.fontFamily || 'Noto Sans JP',
                                fontSize: `${subStyle.fontSize * scale}px`,
                                color: subStyle.color,
                                backgroundColor: subStyle.backgroundColor,
                                textShadow: buildTextShadow(subStyle),
                                fontWeight: subStyle.fontWeight || 'normal',
                                padding: `${4 * scale}px ${12 * scale}px`,
                                borderRadius: `${4 * scale}px`,
                                whiteSpace: 'pre-wrap',
                            }}
                        >
                            {/* Text Prefix (only if no image prefix) */}
                            {(subStyle.prefixImage === null || subStyle.prefixImage === undefined) && subStyle.prefix && `${subStyle.prefix} `}
                            {/* Subtitle Text */}
                            {sub.text}
                        </span>
                    </div>
                );
            })}

            {/* Thumbnail Capture Button */}
            <button
                onClick={handleCaptureThumbnail}
                className="absolute top-4 right-4 bg-black/50 hover:bg-black/70 text-white p-2 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                title="サムネイルを保存"
            >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
            </button>
        </div>
    );
}
