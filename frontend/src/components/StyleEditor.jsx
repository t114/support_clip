import React from 'react';

export default function StyleEditor({ styles, onStyleChange }) {
    const handleChange = (key, value) => {
        onStyleChange({ ...styles, [key]: value });
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

            <div className="grid grid-cols-2 gap-4">
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
