// Graph Visualization Module
let network = null;
let allNodes = [];
let allEdges = [];

function applyGraphFilters() {
    const nodeTypeFilter = Array.from(document.getElementById('nodeTypeFilter').selectedOptions)
        .map(opt => opt.value);
    const relationshipFilter = Array.from(document.getElementById('relationshipFilter').selectedOptions)
        .map(opt => opt.value);
    const nodeLimit = parseInt(document.getElementById('nodeLimit').value);
    
    // Filter nodes
    const filteredNodes = allNodes.filter(node => 
        nodeTypeFilter.includes(node.group)
    ).slice(0, nodeLimit);
    
    // Filter edges based on both node visibility and relationship type
    const visibleNodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredEdges = allEdges.filter(edge => {
        // First check if both connected nodes are visible
        if (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to)) {
            return false;
        }
        
        // Determine node types
        const fromType = edge.from.startsWith('user_') ? 'user' : 
                        edge.from.startsWith('app_') ? 'app' : 'category';
        const toType = edge.to.startsWith('user_') ? 'user' : 
                      edge.to.startsWith('app_') ? 'app' : 'category';
        
        // Check if this relationship type should be shown
        const relationshipType = `${fromType}-${toType}`;
        const reverseRelationshipType = `${toType}-${fromType}`;
        
        // Special case: user-category relationships may go through apps
        if (relationshipFilter.includes('user-category') && 
            ((fromType === 'user' && toType === 'app') || 
             (fromType === 'app' && toType === 'category'))) {
            return true;
        }
        
        return relationshipFilter.includes(relationshipType) || 
               relationshipFilter.includes(reverseRelationshipType);
    });

    // Update the network
    if (network) {
        network.setData({
            nodes: new vis.DataSet(filteredNodes),
            edges: new vis.DataSet(filteredEdges)
        });
        
        // Stabilize the network after filtering
        network.stabilize(100);
    }
}

function buildKnowledgeGraph(data) {
    try {
        // Store all nodes and edges for filtering
        allNodes = data.graph.nodes.map(node => {
            // Format labels differently based on node type
            let label;
            if (node.type === 'User') {
                // For users, show their actual name from the data
                const userId = node.id.replace('user_', '');
                const userName = node.name || `User ${userId}`;
                label = userName;
            } else {
                // For apps and categories, just show the name
                label = node.id.replace(/^(app_|cat_)/, '');
            }
            
            return {
                id: node.id,
                label: label,
                group: node.type.toLowerCase(),
                shape: node.type === 'User' ? 'dot' : 
                       node.type === 'App' ? 'box' : 'diamond',
                size: node.type === 'User' ? 20 : 
                      node.type === 'App' ? 25 : 30,
                // Store original ID for reference
                originalId: node.id
            };
        });

        allEdges = data.graph.edges.map(edge => ({
            from: edge.source,
            to: edge.target,
            label: edge.source.startsWith('user_') ? 'recommends' : 'belongs to'
        }));

        // Apply initial filters
        const container = document.getElementById('knowledgeGraph');
        const filteredNodes = allNodes.slice(0, 500); // Initial limit of 500 nodes
        const visibleNodeIds = new Set(filteredNodes.map(n => n.id));
        const filteredEdges = allEdges.filter(edge => 
            visibleNodeIds.has(edge.from) && visibleNodeIds.has(edge.to)
        );

        // Create the network data
        const graphData = {
            nodes: new vis.DataSet(filteredNodes),
            edges: new vis.DataSet(filteredEdges)
        };

        // Show loading state
        document.getElementById('graphLoader').style.display = 'flex';

        // Create the network with a slight delay to allow loading state to show
        return setTimeout(() => {
            network = new vis.Network(container, graphData, networkOptions);
            document.getElementById('graphLoader').style.display = 'none';
            return network;
        }, 100);

    } catch (error) {
        console.error('Error in buildKnowledgeGraph:', error);
        throw error;
    }
}

// Export the build function for use in the template
window.buildKnowledgeGraph = buildKnowledgeGraph;

// Initialize filter controls
document.addEventListener('DOMContentLoaded', function() {
    // Update node limit display
    document.getElementById('nodeLimit').addEventListener('input', function() {
        document.getElementById('nodeLimitValue').textContent = this.value;
    });

    // Apply filters button
    document.getElementById('applyFilters').addEventListener('click', function() {
        document.getElementById('graphLoader').style.display = 'flex';
        setTimeout(() => {
            applyGraphFilters();
            document.getElementById('graphLoader').style.display = 'none';
        }, 100);
    });

    // Reset filters button
    document.getElementById('resetFilters').addEventListener('click', function() {
        Array.from(document.getElementById('nodeTypeFilter').options)
            .forEach(opt => opt.selected = true);
        Array.from(document.getElementById('relationshipFilter').options)
            .forEach(opt => opt.selected = true);
        document.getElementById('nodeLimit').value = 500;
        document.getElementById('nodeLimitValue').textContent = '500';
        applyGraphFilters();
    });
});

// Optimized network options
const networkOptions = {
    nodes: {
        font: {
            size: 12,
            strokeWidth: 0 // Improves rendering performance
        },
        shadow: false // Improves performance
    },
    edges: {
        arrows: 'to',
        font: {
            size: 10,
            align: 'middle'
        },
        smooth: {
            enabled: true,
            type: 'continuous'
        },
        selectionWidth: 0 // Improves performance
    },
    groups: {
        user: {
            color: '#E57373',
            font: { color: '#D32F2F' }
        },
        app: {
            color: '#81C784',
            font: { color: '#2E7D32' }
        },
        category: {
            color: '#64B5F6',
            font: { color: '#1565C0' }
        }
    },
    physics: {
        stabilization: {
            enabled: true,
            iterations: 50 // Faster stabilization
        },
        barnesHut: {
            gravitationalConstant: -20000, // More spread out
            springLength: 150,
            springConstant: 0.02,
            damping: 0.3
        }
    },
    interaction: {
        multiselect: true,
        hover: true,
        tooltipDelay: 200
    }
};
