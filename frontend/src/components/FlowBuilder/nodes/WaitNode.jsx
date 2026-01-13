import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';

const WaitNode = ({ data, selected }) => {
    const duration = data.config?.duration || 1;
    const unit = data.config?.unit || 'seconds';

    const getUnitLabel = () => {
        const labels = {
            seconds: duration === 1 ? 'segundo' : 'segundos',
            minutes: duration === 1 ? 'minuto' : 'minutos',
            hours: duration === 1 ? 'hora' : 'horas',
            days: duration === 1 ? 'dia' : 'dias'
        };
        return labels[unit] || 'segundos';
    };

    return (
        <div className={`custom-node wait-node ${selected ? 'selected' : ''}`}>
            <div className="node-header">
                <span className="node-icon">⏱️</span>
                <span className="node-title">{data.label || 'Esperar'}</span>
            </div>
            <div className="node-body">
                <div className="node-description">
                    {duration} {getUnitLabel()}
                </div>
            </div>
            <Handle
                type="target"
                position={Position.Top}
                className="custom-handle"
            />
            <Handle
                type="source"
                position={Position.Bottom}
                className="custom-handle"
            />
        </div>
    );
};

export default memo(WaitNode);
