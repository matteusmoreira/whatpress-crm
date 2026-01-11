// Definições de tipos de nós disponíveis no construtor de fluxos

export const NODE_TYPES = {
    START: 'start',
    TEXT_MESSAGE: 'textMessage',
    MEDIA_MESSAGE: 'mediaMessage',
    WAIT: 'wait',
    CONDITIONAL: 'conditional',
    VARIABLE: 'variable',
    WEBHOOK: 'webhook'
};

// Configurações padrão para cada tipo de nó
export const DEFAULT_NODE_DATA = {
    [NODE_TYPES.START]: {
        label: 'Início',
        type: NODE_TYPES.START,
        config: {
            trigger: 'manual', // manual, keyword, schedule
            keyword: '',
            schedule: null
        }
    },
    [NODE_TYPES.TEXT_MESSAGE]: {
        label: 'Enviar Texto',
        type: NODE_TYPES.TEXT_MESSAGE,
        config: {
            message: '',
            variables: []
        }
    },
    [NODE_TYPES.MEDIA_MESSAGE]: {
        label: 'Enviar Mídia',
        type: NODE_TYPES.MEDIA_MESSAGE,
        config: {
            mediaType: 'image', // image, video, document, audio
            mediaUrl: '',
            caption: '',
            variables: []
        }
    },
    [NODE_TYPES.WAIT]: {
        label: 'Esperar',
        type: NODE_TYPES.WAIT,
        config: {
            duration: 1,
            unit: 'seconds' // seconds, minutes, hours, days
        }
    },
    [NODE_TYPES.CONDITIONAL]: {
        label: 'Condicional',
        type: NODE_TYPES.CONDITIONAL,
        config: {
            condition: {
                variable: '',
                operator: 'equals', // equals, contains, greater, less
                value: ''
            },
            branches: [
                { label: 'Verdadeiro', handle: 'true' },
                { label: 'Falso', handle: 'false' }
            ]
        }
    },
    [NODE_TYPES.VARIABLE]: {
        label: 'Variável',
        type: NODE_TYPES.VARIABLE,
        config: {
            action: 'set', // set, get
            variableName: '',
            value: ''
        }
    },
    [NODE_TYPES.WEBHOOK]: {
        label: 'Webhook',
        type: NODE_TYPES.WEBHOOK,
        config: {
            url: '',
            method: 'POST', // GET, POST, PUT, DELETE
            headers: {},
            body: {},
            responseVariable: ''
        }
    }
};

// Descrições dos tipos de nós para o painel lateral
export const NODE_DESCRIPTIONS = {
    [NODE_TYPES.START]: {
        title: 'Início',
        description: 'Ponto de partida do fluxo',
        icon: '🟢',
        category: 'trigger'
    },
    [NODE_TYPES.TEXT_MESSAGE]: {
        title: 'Enviar Texto',
        description: 'Envia uma mensagem de texto',
        icon: '💬',
        category: 'action'
    },
    [NODE_TYPES.MEDIA_MESSAGE]: {
        title: 'Enviar Mídia',
        description: 'Envia imagem, vídeo ou documento',
        icon: '📎',
        category: 'action'
    },
    [NODE_TYPES.WAIT]: {
        title: 'Esperar',
        description: 'Aguarda um tempo antes de continuar',
        icon: '⏱️',
        category: 'control'
    },
    [NODE_TYPES.CONDITIONAL]: {
        title: 'Condicional',
        description: 'Ramifica o fluxo baseado em condições',
        icon: '🔀',
        category: 'control'
    },
    [NODE_TYPES.VARIABLE]: {
        title: 'Variável',
        description: 'Define ou usa variáveis no fluxo',
        icon: '📝',
        category: 'data'
    },
    [NODE_TYPES.WEBHOOK]: {
        title: 'Webhook',
        description: 'Chama uma API externa',
        icon: '🌐',
        category: 'integration'
    }
};

// Categorias de nós
export const NODE_CATEGORIES = {
    trigger: { label: 'Gatilhos', order: 1 },
    action: { label: 'Ações', order: 2 },
    control: { label: 'Controle', order: 3 },
    data: { label: 'Dados', order: 4 },
    integration: { label: 'Integrações', order: 5 }
};

// Validates uma estrutura de fluxo
export const validateFlow = (nodes, edges) => {
    const errors = [];

    // Verificar se tem nó de início
    const startNodes = nodes.filter(n => n.type === NODE_TYPES.START);
    if (startNodes.length === 0) {
        errors.push('O fluxo deve ter pelo menos um nó de início');
    }
    if (startNodes.length > 1) {
        errors.push('O fluxo deve ter apenas um nó de início');
    }

    // Verificar nós órfãos (exceto o nó de início)
    const connectedNodeIds = new Set();
    edges.forEach(edge => {
        connectedNodeIds.add(edge.source);
        connectedNodeIds.add(edge.target);
    });

    const orphanNodes = nodes.filter(node =>
        node.type !== NODE_TYPES.START && !connectedNodeIds.has(node.id)
    );

    if (orphanNodes.length > 0) {
        errors.push(`${orphanNodes.length} nó(s) desconectado(s) encontrado(s)`);
    }

    // Verificar se todos os nós têm configuração válida
    nodes.forEach(node => {
        if (!node.data || !node.data.config) {
            errors.push(`Nó "${node.data?.label || node.id}" sem configuração`);
        }

        // Validações específicas por tipo
        switch (node.type) {
            case NODE_TYPES.TEXT_MESSAGE:
                if (!node.data?.config?.message?.trim()) {
                    errors.push(`Nó "${node.data?.label || node.id}": mensagem de texto vazia`);
                }
                break;
            case NODE_TYPES.MEDIA_MESSAGE:
                if (!node.data?.config?.mediaUrl?.trim()) {
                    errors.push(`Nó "${node.data?.label || node.id}": URL da mídia não definida`);
                }
                break;
            case NODE_TYPES.WEBHOOK:
                if (!node.data?.config?.url?.trim()) {
                    errors.push(`Nó "${node.data?.label || node.id}": URL do webhook não definida`);
                }
                break;
            case NODE_TYPES.VARIABLE:
                if (!node.data?.config?.variableName?.trim()) {
                    errors.push(`Nó "${node.data?.label || node.id}": nome da variável não definido`);
                }
                break;
            case NODE_TYPES.WAIT:
                if (!node.data?.config?.duration || node.data.config.duration <= 0) {
                    errors.push(`Nó "${node.data?.label || node.id}": duração de espera inválida`);
                }
                break;
            default:
                break;
        }
    });

    // Verificar loops infinitos (básico)
    const hasPath = (from, to, visited = new Set()) => {
        if (from === to) return true;
        if (visited.has(from)) return false;
        visited.add(from);

        const outgoingEdges = edges.filter(e => e.source === from);
        return outgoingEdges.some(e => hasPath(e.target, to, new Set(visited)));
    };

    nodes.forEach(node => {
        if (hasPath(node.id, node.id)) {
            errors.push(`Loop infinito detectado no nó "${node.data?.label || node.id}"`);
        }
    });

    return {
        isValid: errors.length === 0,
        errors
    };
};

// Gera ID único para nós
export const generateNodeId = (type) => {
    return `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

// Cria um novo nó com configurações padrão
export const createNode = (type, position = { x: 0, y: 0 }) => {
    const nodeData = DEFAULT_NODE_DATA[type];

    if (!nodeData) {
        throw new Error(`Tipo de nó desconhecido: ${type}`);
    }

    return {
        id: generateNodeId(type),
        type,
        position,
        data: { ...nodeData }
    };
};
