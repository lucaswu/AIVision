import React from 'react';
import { Button, Tooltip } from 'antd';
import {
  GatewayOutlined,
  CloseOutlined // 新增关闭按钮
} from "@ant-design/icons";

// 定义绘图类型
export type DrawingType = 'select' | 'rect' | 'polygon' | 'circle' | 'brush';

interface DefectMarkingProps {
  currentType: DrawingType;    // 当前选中的工具类型
  onTypeChange: (type: DrawingType) => void; // 切换工具的回调
  onClose?: () => void;        // 关闭工具条
}

const DefectMarking: React.FC<DefectMarkingProps> = ({
  currentType,
  onTypeChange,
  onClose
}) => {
  
  // 样式辅助函数：选中显示蓝色
  const getButtonStyle = (type: DrawingType) => ({
    width: 40, 
    height: 40,
    color: currentType === type ? '#fff' : 'rgba(255, 255, 255, 0.85)',
    background: currentType === type ? '#1890ff' : 'transparent',
    border: currentType === type ? 'none' : '1px solid #434343',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center'
  });

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      gap: '12px', 
      background: '#363636ff', // 深色背景
      padding: '12px 8px', 
      borderRadius: '8px',
      boxShadow: '0 4px 12px rgba(248, 247, 247, 0.5)',
      border: '1px solid #faf8f8ff',
      width: '58px', // 固定宽度
      alignItems: 'center',
      zIndex: 200 // 保证在最上层
    }}>
        
        {/* 工具按钮组 */}
        <Tooltip title="多边形(单击左键设置点,双击结束)" placement="right">
          <Button type="text" shape="circle" icon={<GatewayOutlined rotate={180}/>} style={getButtonStyle('polygon')} onClick={() => onTypeChange('polygon')} />
        </Tooltip>

        {/* 分割线 */}
        <div style={{ width: '80%', height: 1, background: '#434343', margin: '4px 0' }} />

        {onClose && (
           <Tooltip title="退出标注模式" placement="right">
             <Button 
               danger 
               type="text" 
               shape="circle" 
               icon={<CloseOutlined />} 
               style={{ width: 40, height: 40, color: '#ff4d4f', border: '1px solid #5c2b2b' }}
               onClick={onClose}
             />
           </Tooltip>
        )}
    </div>
  );
};

export default DefectMarking;