import React from 'react';

export default function StyleEditor({ styles, onStyleChange, savedStyles, onSave, onLoad, onDelete, defaultStyleName, onSetDefault, onStyleUsed }) {
    const [styleName, setStyleName] = React.useState('');
    const [searchTerm, setSearchTerm] = React.useState('');

    const handleChange = (key, value) => {
        onStyleChange({ ...styles, [key]: value });
    };

    const handleSave = () => {
        if (styleName.trim()) {
            onSave(styleName.trim(), styles);
            setStyleName('');
        }
    };

    // Helper to get hex and alpha from #RRGGBBAA
    const getHexAndAlpha = (color) => {
        if (!color) return { hex: '#000000', alpha: 128 };
        const hex = color.slice(0, 7);
        const alphaHex = color.slice(7, 9) || 'FF';
        const alpha = parseInt(alphaHex, 16);
        return { hex, alpha };
    };

    const { hex: bgHex, alpha: bgAlpha } = getHexAndAlpha(styles.backgroundColor);

    const handleBgColorChange = (e) => {
        const newHex = e.target.value;
        const alphaHex = bgAlpha.toString(16).padStart(2, '0');
        handleChange('backgroundColor', `${newHex}${alphaHex}`);
    };

    const handleOpacityChange = (e) => {
        const newAlpha = parseInt(e.target.value);
        const alphaHex = newAlpha.toString(16).padStart(2, '0');
        handleChange('backgroundColor', `${bgHex}${alphaHex}`);
    };

    return (
        <div className="bg-white p-4 rounded-lg shadow space-y-4">
            <h3 className="font-bold text-gray-700">字幕スタイル</h3>

            {/* スタイル保存・読み込み */}
            <div className="bg-gray-50 p-3 rounded border border-gray-200 mb-4">
                <div className="flex gap-2 mb-2">
                    <input
                        type="text"
                        value={styleName}
                        onChange={(e) => setStyleName(e.target.value)}
                        placeholder="スタイル名を入力"
                        className="flex-1 border border-gray-300 rounded px-2 py-1 text-sm"
                    />
                    <button
                        onClick={handleSave}
                        disabled={!styleName.trim()}
                        className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700 disabled:bg-gray-300"
                    >
                        {savedStyles && savedStyles[styleName] ? '更新' : '保存'}
                    </button>
                </div>

                {savedStyles && Object.keys(savedStyles).length > 0 && (
                    <div className="space-y-2">
                        <label className="block text-xs text-gray-600">保存済みスタイル:</label>
                        <input
                            type="text"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            placeholder="スタイルを検索..."
                            className="w-full border border-gray-300 rounded px-2 py-1 text-sm mb-2"
                        />
                        <div className="flex flex-wrap gap-2">
                            {Object.keys(savedStyles)
                                .filter(name => name.toLowerCase().includes(searchTerm.toLowerCase()))
                                .length > 0 ? (
                                Object.keys(savedStyles)
                                    .filter(name => name.toLowerCase().includes(searchTerm.toLowerCase()))
                                    .map(name => (
                                        <div
                                            key={name}
                                            className={`flex items-center border rounded px-2 py-1 text-sm ${defaultStyleName === name
                                                ? 'bg-blue-100 border-blue-400'
                                                : 'bg-white border-gray-300'
                                                }`}
                                        >
                                            {defaultStyleName === name && (
                                                <span className="text-blue-600 mr-1 text-xs">★</span>
                                            )}
                                            <span
                                                className="cursor-pointer hover:text-blue-600 mr-2"
                                                onClick={() => {
                                                    onLoad(name);
                                                    setStyleName(name);
                                                    if (onStyleUsed) onStyleUsed(name);
                                                }}
                                            >
                                                {name}
                                            </span>
                                            {onSetDefault && (
                                                <button
                                                    onClick={() => onSetDefault(defaultStyleName === name ? '' : name)}
                                                    className={`text-xs mr-1 ${defaultStyleName === name
                                                        ? 'text-blue-600 hover:text-blue-800'
                                                        : 'text-gray-400 hover:text-blue-600'
                                                        }`}
                                                    title={defaultStyleName === name ? 'デフォルト解除' : 'デフォルトに設定'}
                                                >
                                                    {defaultStyleName === name ? '★' : '☆'}
                                                </button>
                                            )}
                                            <button
                                                onClick={() => onDelete(name)}
                                                className="text-red-500 hover:text-red-700 text-xs"
                                            >
                                                ✕
                                            </button>
                                        </div>
                                    ))
                            ) : (
                                <div className="w-full text-center text-sm text-gray-500 italic py-2">
                                    「{searchTerm}」に一致するスタイルが見つかりません
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">プレフィックス</label>
                    <div className="space-y-2">
                        {/* Text or Image Toggle */}
                        <div className="flex gap-4">
                            <label className="flex items-center cursor-pointer">
                                <input
                                    type="radio"
                                    name="prefixType"
                                    checked={styles.prefixImage === null || styles.prefixImage === undefined}
                                    onChange={() => handleChange('prefixImage', null)}
                                    className="mr-2"
                                />
                                <span className="text-sm">テキスト</span>
                            </label>
                            <label className="flex items-center cursor-pointer">
                                <input
                                    type="radio"
                                    name="prefixType"
                                    checked={styles.prefixImage !== null && styles.prefixImage !== undefined}
                                    onChange={() => {
                                        // Update both properties at once to avoid state update conflicts
                                        onStyleChange({ ...styles, prefixImage: '', prefix: '' });
                                    }}
                                    className="mr-2"
                                />
                                <span className="text-sm">画像</span>
                            </label>
                        </div>

                        {/* Text Prefix Input */}
                        {(styles.prefixImage === null || styles.prefixImage === undefined) && (
                            <input
                                type="text"
                                value={styles.prefix || ''}
                                onChange={(e) => handleChange('prefix', e.target.value)}
                                placeholder="例: 💬"
                                className="w-full border border-gray-300 rounded px-2 py-1"
                            />
                        )}

                        {/* Image Upload */}
                        {(styles.prefixImage !== null && styles.prefixImage !== undefined) && (
                            <div className="space-y-2">
                                <input
                                    type="file"
                                    accept="image/*"
                                    onChange={async (e) => {
                                        const file = e.target.files?.[0];
                                        if (!file) return;

                                        // Upload to backend
                                        const formData = new FormData();
                                        formData.append('file', file);

                                        try {
                                            const response = await fetch('/upload-prefix-image', {
                                                method: 'POST',
                                                body: formData,
                                            });

                                            if (!response.ok) {
                                                throw new Error('Upload failed');
                                            }

                                            const data = await response.json();
                                            // Update both properties at once
                                            onStyleChange({ ...styles, prefixImage: data.image_url, prefix: '' });
                                        } catch (error) {
                                            console.error('Error uploading image:', error);
                                            alert('画像のアップロードに失敗しました');
                                        }
                                    }}
                                    className="w-full text-sm"
                                />

                                {/* Image Size Controls */}
                                <div className="flex items-center gap-2">
                                    <label className="text-xs text-gray-600">サイズ:</label>
                                    <input
                                        type="number"
                                        value={styles.prefixImageSize || 32}
                                        onChange={(e) => handleChange('prefixImageSize', Number(e.target.value))}
                                        min="16"
                                        max="128"
                                        className="border border-gray-300 rounded px-2 py-1 w-20 text-sm"
                                    />
                                    <span className="text-xs text-gray-500">px</span>
                                </div>

                                {/* Image Preview */}
                                {styles.prefixImage && (
                                    <div className="flex items-center gap-2">
                                        <img
                                            src={styles.prefixImage}
                                            alt="Prefix"
                                            style={{ height: `${styles.prefixImageSize || 32}px`, width: 'auto' }}
                                            className="border border-gray-300 rounded"
                                        />
                                        <button
                                            onClick={() => {
                                                // Clear image but stay in image mode
                                                handleChange('prefixImage', '');
                                            }}
                                            className="text-red-500 hover:text-red-700 text-xs"
                                        >
                                            画像削除
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">文字サイズ (px)</label>
                    <input
                        type="number"
                        value={styles.fontSize}
                        onChange={(e) => handleChange('fontSize', Number(e.target.value))}
                        className="w-full border border-gray-300 rounded px-2 py-1"
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">位置 (下からの%)</label>
                    <input
                        type="number"
                        value={styles.bottom}
                        onChange={(e) => handleChange('bottom', Number(e.target.value))}
                        className="w-full border border-gray-300 rounded px-2 py-1"
                    />
                </div>

                <div>
                    <select
                        value={styles.alignment || 'center'}
                        onChange={(e) => handleChange('alignment', e.target.value)}
                        className="w-full border border-gray-300 rounded px-2 py-1"
                    >
                        <option value="left">左寄せ</option>
                        <option value="center">中央</option>
                        <option value="right">右寄せ</option>
                        <option value="top-left">上部・左</option>
                        <option value="top">上部・中央</option>
                        <option value="top-right">上部・右</option>
                    </select>
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">改行時の展開方向</label>
                    <select
                        value={styles.verticalDirection || 'up'}
                        onChange={(e) => handleChange('verticalDirection', e.target.value)}
                        className="w-full border border-gray-300 rounded px-2 py-1"
                        title="改行した時に、基準位置から上に向かって積み上げるか、下に向かって伸ばすかを設定します"
                    >
                        <option value="up">上へ (通常)</option>
                        <option value="down">下へ</option>
                    </select>
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">フォント</label>
                    <div className="space-y-2">
                        <select
                            value={styles.fontFamily || 'Noto Sans JP'}
                            onChange={(e) => handleChange('fontFamily', e.target.value)}
                            className="w-full border border-gray-300 rounded px-2 py-1"
                        >
                            <option value="Noto Sans JP">Noto Sans JP (標準)</option>
                            <option value="Klee One">Klee One (手書き風)</option>
                            <option value="Dela Gothic One">Dela Gothic One (太文字)</option>
                            <option value="Kilgo U">キルゴU (要ファイル)</option>
                        </select>
                        <div className="flex items-center">
                            <input
                                type="checkbox"
                                id="fontWeight"
                                checked={styles.fontWeight === 'bold'}
                                onChange={(e) => handleChange('fontWeight', e.target.checked ? 'bold' : 'normal')}
                                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                            />
                            <label htmlFor="fontWeight" className="ml-2 block text-sm text-gray-900">
                                太字にする
                            </label>
                        </div>
                    </div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">文字色</label>
                    <div className="flex items-center space-x-2">
                        <input
                            type="color"
                            value={styles.color}
                            onChange={(e) => handleChange('color', e.target.value)}
                            className="h-8 w-8 rounded cursor-pointer"
                        />
                        <span className="text-sm text-gray-500">{styles.color}</span>
                    </div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">背景色・透明度</label>
                    <div className="space-y-2">
                        <div className="flex items-center space-x-2">
                            <input
                                type="color"
                                value={bgHex}
                                onChange={handleBgColorChange}
                                className="h-8 w-8 rounded cursor-pointer"
                            />
                            <span className="text-sm text-gray-500">{bgHex}</span>
                        </div>
                        <div className="flex items-center space-x-2">
                            <input
                                type="range"
                                min="0"
                                max="255"
                                value={bgAlpha}
                                onChange={handleOpacityChange}
                                className="w-full"
                            />
                            <span className="text-sm text-gray-500 w-12 text-right">
                                {Math.round((bgAlpha / 255) * 100)}%
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* 縁取り設定 */}
            <div className="border-t pt-4">
                <h4 className="font-semibold text-gray-700 mb-3">縁取り設定</h4>
                <div className="grid grid-cols-2 gap-4">
                    {/* 内側の縁取り */}
                    <div className="col-span-2">
                        <label className="block text-sm font-medium text-gray-700 mb-2">内側の縁取り</label>
                        <div className="grid grid-cols-2 gap-2">
                            <div>
                                <label className="block text-xs text-gray-600 mb-1">色</label>
                                <input
                                    type="color"
                                    value={styles.outlineColor || '#000000'}
                                    onChange={(e) => handleChange('outlineColor', e.target.value)}
                                    className="h-8 w-full rounded cursor-pointer"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-600 mb-1">太さ (px)</label>
                                <input
                                    type="number"
                                    min="0"
                                    max="10"
                                    value={styles.outlineWidth || 0}
                                    onChange={(e) => handleChange('outlineWidth', Number(e.target.value))}
                                    className="w-full border border-gray-300 rounded px-2 py-1"
                                />
                            </div>
                        </div>
                    </div>

                    {/* 外側の縁取り */}
                    <div className="col-span-2">
                        <label className="block text-sm font-medium text-gray-700 mb-2">外側の縁取り</label>
                        <div className="grid grid-cols-2 gap-2">
                            <div>
                                <label className="block text-xs text-gray-600 mb-1">色</label>
                                <input
                                    type="color"
                                    value={styles.outerOutlineColor || '#FFFFFF'}
                                    onChange={(e) => handleChange('outerOutlineColor', e.target.value)}
                                    className="h-8 w-full rounded cursor-pointer"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-600 mb-1">太さ (px)</label>
                                <input
                                    type="number"
                                    min="0"
                                    max="10"
                                    value={styles.outerOutlineWidth || 0}
                                    onChange={(e) => handleChange('outerOutlineWidth', Number(e.target.value))}
                                    className="w-full border border-gray-300 rounded px-2 py-1"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* 影設定 */}
            <div className="border-t pt-4">
                <h4 className="font-semibold text-gray-700 mb-3">影設定</h4>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm text-gray-600 mb-1">影の色</label>
                        <input
                            type="color"
                            value={styles.shadowColor || '#000000'}
                            onChange={(e) => handleChange('shadowColor', e.target.value)}
                            className="h-8 w-full rounded cursor-pointer"
                        />
                    </div>
                    <div>
                        <label className="block text-sm text-gray-600 mb-1">影のぼかし (px)</label>
                        <input
                            type="number"
                            min="0"
                            max="20"
                            value={styles.shadowBlur || 0}
                            onChange={(e) => handleChange('shadowBlur', Number(e.target.value))}
                            className="w-full border border-gray-300 rounded px-2 py-1"
                        />
                    </div>
                    <div>
                        <label className="block text-sm text-gray-600 mb-1">影のX位置 (px)</label>
                        <input
                            type="number"
                            min="-20"
                            max="20"
                            value={styles.shadowOffsetX || 0}
                            onChange={(e) => handleChange('shadowOffsetX', Number(e.target.value))}
                            className="w-full border border-gray-300 rounded px-2 py-1"
                        />
                    </div>
                    <div>
                        <label className="block text-sm text-gray-600 mb-1">影のY位置 (px)</label>
                        <input
                            type="number"
                            min="-20"
                            max="20"
                            value={styles.shadowOffsetY || 0}
                            onChange={(e) => handleChange('shadowOffsetY', Number(e.target.value))}
                            className="w-full border border-gray-300 rounded px-2 py-1"
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
