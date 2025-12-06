import React, { useState } from 'react';

export default function Upload({ onUploadStart, onUploadSuccess, onUploadError }) {
    const [modelSize, setModelSize] = useState('base');
    const [isDragging, setIsDragging] = useState(false);

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadFile(files[0]);
        }
    };

    const handleFileSelect = (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    };

    const uploadFile = async (file) => {
        if (!file.type.startsWith('video/')) {
            alert('動画ファイルを選択してください。');
            return;
        }

        onUploadStart();
        const formData = new FormData();
        formData.append('file', file);
        formData.append('model_size', modelSize);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('アップロードに失敗しました');
            }

            const data = await response.json();
            onUploadSuccess(data);
        } catch (error) {
            console.error(error);
            onUploadError(error.message);
        }
    };

    return (
        <div
            className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
                }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            <div className="space-y-4">
                <div className="text-4xl">📹</div>
                <h3 className="text-lg font-medium text-gray-900">
                    動画をアップロード
                </h3>
                <p className="text-gray-500">
                    ここに動画をドラッグ＆ドロップするか、クリックして選択してください
                </p>

                <div className="flex justify-center items-center gap-2 mt-4">
                    <label className="text-sm text-gray-600">モデル:</label>
                    <select
                        value={modelSize}
                        onChange={(e) => setModelSize(e.target.value)}
                        className="p-1 border rounded bg-white text-sm"
                        onClick={(e) => e.stopPropagation()} // Prevent triggering drop zone click
                    >
                        <option value="tiny">tiny (最速・低精度)</option>
                        <option value="base">base (推奨・バランス)</option>
                        <option value="small">small (高精度・遅い)</option>
                        <option value="medium">medium (超高精度・激遅)</option>
                        <option value="large">large (最高精度・激重)</option>
                    </select>
                </div>

                <input
                    type="file"
                    accept="video/*"
                    className="hidden"
                    id="file-upload"
                    onChange={handleFileSelect}
                />
                <label
                    htmlFor="file-upload"
                    className="inline-block px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 cursor-pointer transition-colors"
                >
                    ファイルを選択
                </label>
            </div>
        </div>
    );
}
