import React from 'react';
import { Button, Tooltip } from 'antd';
import {
    CloseOutlined
} from "@ant-design/icons";

export type PositionSizeType = 'elliptical' | 'vertical' | 'positioning';

interface PositionAndSizeToolProps {
    currentType: PositionSizeType | null;
    onTypeChange: (type: PositionSizeType) => void;
    onClose: () => void;
}

const PositionAndSizeTool: React.FC<PositionAndSizeToolProps> = ({
    currentType,
    onTypeChange,
    onClose
}) => {

    const getButtonStyle = (type: PositionSizeType) => ({
        width: 40,
        height: 40,
        color: currentType === type ? '#fff' : 'rgba(255, 255, 255, 0.85)',
        background: currentType === type ? '#1890ff' : 'transparent',
        border: currentType === type ? 'none' : '1px solid #434343',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 0
    });

    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            background: '#363636ff',
            padding: '12px 8px',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(248, 247, 247, 0.5)',
            border: '1px solid #faf8f8ff',
            width: '58px',
            alignItems: 'center',
            zIndex: 200
        }}>

            {/* 1. 椭圆成像 */}
            <Tooltip title="椭圆成像" placement="right">
                <Button
                    type="text"
                    shape="circle"
                    onClick={() => onTypeChange('elliptical')}
                    style={getButtonStyle('elliptical')}
                >
                    {/* 使用一个 CSS 绘制的椭圆图标作占位 */}
                    <div style={{
                        width: '20px',
                        height: '14px',
                        border: '2px solid currentColor',
                        borderRadius: '50%'
                    }} />
                </Button>
            </Tooltip>

            {/* 2. 垂直成像 */}
            <Tooltip title="垂直成像" placement="right">
                <Button
                    type="text"
                    shape="circle"
                    onClick={() => onTypeChange('vertical')}
                    style={getButtonStyle('vertical')}
                >
                    <img
                        src="/align-vertical-justify-center.svg"
                        alt="vertical"
                        style={{
                            width: 20,
                            height: 20,
                            filter: 'invert(1)' // 图标如果是黑色需要反色
                        }}
                    />
                </Button>
            </Tooltip>

            {/* 3. 定位标记成像 */}
            <Tooltip title="定位标记成像" placement="right">
                <Button
                    type="text"
                    shape="circle"
                    onClick={() => onTypeChange('positioning')}
                    style={getButtonStyle('positioning')}
                >
                    <img
                        src="/circle-plus.svg"
                        alt="positioning"
                        style={{
                            width: 20,
                            height: 20,
                            filter: 'invert(1)'
                        }}
                    />
                </Button>
            </Tooltip>

            <div style={{ width: '80%', height: 1, background: '#434343', margin: '4px 0' }} />

            {/* 4. 退出 */}
            <Tooltip title="退出工具" placement="right">
                <Button
                    danger
                    type="text"
                    shape="circle"
                    icon={<CloseOutlined />}
                    style={{ width: 40, height: 40, color: '#ff4d4f', border: '1px solid #5c2b2b' }}
                    onClick={onClose}
                />
            </Tooltip>
        </div>
    );
};

export default PositionAndSizeTool;
