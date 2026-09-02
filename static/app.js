// -------------------------------------------------------------
// APP CONFIG & GLOBAL VARIABLES
// -------------------------------------------------------------
let networkInstance = null;
let nodesDataSet = null;
let edgesDataSet = null;
let originalNodesList = [];
let originalEdgesList = [];
let isHierarchical = false;

// Node style configuration variables matching CSS theme
const entityStyles = {
    Supplier: { background: "#3b82f6", border: "#60a5fa", font: "#ffffff" },
    PurchaseOrder: { background: "#eab308", border: "#facc15", font: "#0f172a" },
    Part: { background: "#f97316", border: "#fb923c", font: "#ffffff" },
    Product: { background: "#10b981", border: "#34d399", font: "#ffffff" },
    Plant: { background: "#8b5cf6", border: "#a78bfa", font: "#ffffff" },
    Default: { background: "#64748b", border: "#94a3b8", font: "#ffffff" }
};

const highlightColor = {
    background: "#ec4899", // Neon Hot Pink
    border: "#f472b6",
    font: "#ffffff"
};

// -------------------------------------------------------------
// 1. INITIALIZE GRAPH NETWORK ON LOAD
// -------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    initGraph();
    setupEventListeners();
});

function initGraph() {
    const canvasContainer = document.getElementById("graph-canvas");
    
    // Fetch all nodes and edges from the FastAPI server
    fetch("/api/graph-data")
        .then(response => {
            if (!response.ok) throw new Error("Failed to fetch graph structure.");
            return response.json();
        })
        .then(data => {
            originalNodesList = data.nodes;
            originalEdgesList = data.edges;
            
            // Format nodes for Vis.js
            const formattedNodes = data.nodes.map(node => {
                const style = entityStyles[node.type] || entityStyles.Default;
                const levelMapping = { Supplier: 0, PurchaseOrder: 1, Part: 2, Plant: 2, Product: 3 };
                return {
                    id: node.id,
                    label: `${node.label}\n(${node.type})`,
                    shape: "dot",
                    size: 15,
                    font: { color: "#f8fafc", size: 10, face: "Inter" },
                    color: {
                        background: style.background,
                        border: style.border,
                        highlight: { background: style.background, border: style.border }
                    },
                    level: levelMapping[node.type] !== undefined ? levelMapping[node.type] : 2,
                    title: formatTooltip(node.type, node.properties) // HTML tooltip on hover
                };
            });
            
            // Format edges for Vis.js
            const formattedEdges = data.edges.map((edge, index) => {
                return {
                    id: `edge-${index}`,
                    from: edge.from,
                    to: edge.to,
                    label: edge.label,
                    arrows: "to",
                    font: { color: "#64748b", size: 8, align: "horizontal", face: "Inter" },
                    color: { color: "rgba(255, 255, 255, 0.15)", highlight: "#94a3b8" },
                    width: 1
                };
            });
            
            // Create Vis.js DataSets (allows dynamic real-time updates)
            nodesDataSet = new vis.DataSet(formattedNodes);
            edgesDataSet = new vis.DataSet(formattedEdges);
            
            const graphData = { nodes: nodesDataSet, edges: edgesDataSet };
            
            // Define Vis.js Configuration options
            const options = {
                physics: {
                    solver: "forceAtlas2Based",
                    forceAtlas2Based: {
                        gravitationalConstant: -35,
                        centralGravity: 0.015,
                        springLength: 80,
                        springConstant: 0.06
                    },
                    stabilization: { iterations: 150, updateInterval: 25 }
                },
                interaction: {
                    hover: true,
                    dragNodes: true,
                    zoomView: true
                }
            };
            
            // Render the network
            networkInstance = new vis.Network(canvasContainer, graphData, options);
            
            // Listen to select events for sidebar
            networkInstance.on("selectNode", (params) => {
                const nodeId = params.nodes[0];
                showNodeDetailsSidebar(nodeId);
            });
            
            networkInstance.on("deselectNode", () => {
                hideNodeDetailsSidebar();
            });
        })
        .catch(err => {
            console.error("Error loading network graph: ", err);
            canvasContainer.innerHTML = `<div class='error-msg'>Connection failed. Could not load supply chain database map.</div>`;
        });
}

function formatTooltip(type, props) {
    let tooltip = `<strong>Node type: ${type}</strong><br>`;
    for (const [key, value] of Object.entries(props)) {
        if (key !== "id") {
            tooltip += `${key}: ${value || "N/A"}<br>`;
        }
    }
    return tooltip;
}

// -------------------------------------------------------------
// NODE PROPERTIES SIDEBAR CONTROLLER
// -------------------------------------------------------------
function showNodeDetailsSidebar(nodeId) {
    const sidebar = document.getElementById("node-sidebar");
    const typeEl = document.getElementById("sidebar-node-type");
    const labelEl = document.getElementById("sidebar-node-label");
    const propertiesEl = document.getElementById("sidebar-properties");
    
    if (!sidebar || !typeEl || !labelEl || !propertiesEl) return;
    
    // Find node properties in the original list
    const node = originalNodesList.find(n => n.id === nodeId);
    if (!node) return;
    
    // Set type and label
    typeEl.textContent = node.type;
    labelEl.textContent = node.label;
    
    // Apply type-specific color accent to the title border
    const style = entityStyles[node.type] || entityStyles.Default;
    labelEl.style.borderBottomColor = style.background;
    
    // Populate properties
    propertiesEl.innerHTML = "";
    
    const props = node.properties || {};
    for (const [key, value] of Object.entries(props)) {
        if (key === "id") continue; // skip internal IDs
        
        const propGroup = document.createElement("div");
        propGroup.className = "property-group";
        
        const label = document.createElement("span");
        label.className = "property-label";
        label.textContent = key.replace(/_/g, " ");
        
        const val = document.createElement("span");
        val.className = "property-value";
        val.textContent = value || "N/A";
        
        propGroup.appendChild(label);
        propGroup.appendChild(val);
        propertiesEl.appendChild(propGroup);
    }
    
    // Add active class to animate slide-in
    sidebar.classList.add("active");
}

function hideNodeDetailsSidebar() {
    const sidebar = document.getElementById("node-sidebar");
    if (sidebar) {
        sidebar.classList.remove("active");
    }
}

// -------------------------------------------------------------
// 2. QUERY ORCHESTRATION & STEPPER PROGRESS CONTROLLER
// -------------------------------------------------------------
function setupEventListeners() {
    const form = document.getElementById("query-form");
    const quickButtons = document.querySelectorAll(".quick-btn");
    const resetBtn = document.getElementById("reset-graph-btn");
    const toggleLayoutBtn = document.getElementById("toggle-layout-btn");
    
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        const question = document.getElementById("query-input").value.trim();
        if (question) executeQueryPipeline(question);
    });
    
    // Quick Demo Buttons
    quickButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const queryText = btn.getAttribute("data-query");
            document.getElementById("query-input").value = queryText;
            executeQueryPipeline(queryText);
        });
    });
    
    // Reset Map Button
    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            document.getElementById("query-input").value = "";
            // Hide result panels
            document.getElementById("stepper-section").classList.add("hidden");
            document.getElementById("code-section").classList.add("hidden");
            document.getElementById("response-section").classList.add("hidden");
            document.getElementById("citations-section").classList.add("hidden");
            hideNodeDetailsSidebar();
            restoreFullGraph();
        });
    }

    // Close Sidebar Button
    const closeSidebarBtn = document.getElementById("close-sidebar-btn");
    if (closeSidebarBtn) {
        closeSidebarBtn.addEventListener("click", () => {
            if (networkInstance) {
                networkInstance.unselectNodes();
            }
            hideNodeDetailsSidebar();
        });
    }

    // Toggle Hierarchical Layout Button
    if (toggleLayoutBtn) {
        toggleLayoutBtn.addEventListener("click", () => {
            isHierarchical = !isHierarchical;
            if (!networkInstance) return;
            
            if (isHierarchical) {
                toggleLayoutBtn.textContent = "Standard Map";
                toggleLayoutBtn.style.background = "#ec4899"; // Highlight button in hot pink
                toggleLayoutBtn.style.borderColor = "#ec4899";
                
                networkInstance.setOptions({
                    layout: {
                        hierarchical: {
                            enabled: true,
                            direction: "LR", // Force Left-to-Right layout
                            nodeSpacing: 150,
                            levelSeparation: 200,
                            parentCentralization: true
                        }
                    },
                    physics: {
                        enabled: false // Disable physics to avoid hierarchy bouncing
                    }
                });
            } else {
                toggleLayoutBtn.textContent = "Hierarchical Flow";
                toggleLayoutBtn.style.background = "rgba(255, 255, 255, 0.08)";
                toggleLayoutBtn.style.borderColor = "transparent";
                
                // Clear any stored hierarchical positions to let gravity float nodes
                const updates = [];
                nodesDataSet.forEach(node => {
                    updates.push({ id: node.id, x: undefined, y: undefined });
                });
                nodesDataSet.update(updates);
                
                networkInstance.setOptions({
                    layout: {
                        hierarchical: {
                            enabled: false // Disable hierarchical layout safely without crashing Vis.js
                        }
                    },
                    physics: {
                        enabled: true,
                        solver: "forceAtlas2Based",
                        forceAtlas2Based: {
                            gravitationalConstant: -35,
                            centralGravity: 0.015,
                            springLength: 80,
                            springConstant: 0.06
                        }
                    }
                });
            }
            
            // Re-fit graph viewport with a smooth transition
            setTimeout(() => {
                networkInstance.fit({
                    animation: { duration: 600, easingFunction: "easeInOutQuad" }
                });
            }, 200);
        });
    }
}

function updateStepStatus(stepNum, status) {
    const stepEl = document.getElementById(`step-${stepNum}`);
    if (!stepEl) return;
    
    // Reset classes
    stepEl.classList.remove("active", "completed");
    
    if (status === "active") {
        stepEl.classList.add("active");
    } else if (status === "completed") {
        stepEl.classList.add("completed");
    }
}

function executeQueryPipeline(question) {
    // Reset visual overlays
    document.getElementById("stepper-section").classList.remove("hidden");
    document.getElementById("code-section").classList.add("hidden");
    document.getElementById("response-section").classList.add("hidden");
    document.getElementById("citations-section").classList.add("hidden");
    hideNodeDetailsSidebar();
    
    // Set Step 1 active: Translation
    updateStepStatus(1, "active");
    updateStepStatus(2, "pending");
    updateStepStatus(3, "pending");
    updateStepStatus(4, "pending");
    
    // Call server API
    fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question })
    })
        .then(response => {
            // Update step states showing translation finished and database search starting
            updateStepStatus(1, "completed");
            updateStepStatus(2, "active");
            
            if (!response.ok) throw new Error("GraphRAG query execution failed.");
            return response.json();
        })
        .then(data => {
            // Database query finished
            updateStepStatus(2, "completed");
            updateStepStatus(3, "active");
            
            // Visual Hop Animation
            highlightTraversalPath(data.highlighted_nodes);
            
            setTimeout(() => {
                updateStepStatus(3, "completed");
                updateStepStatus(4, "active");
                
                // Render outputs
                renderResults(data);
                
                updateStepStatus(4, "completed");
            }, 800); // Small delay to let user see graph highlight animation
        })
        .catch(err => {
            console.error(err);
            updateStepStatus(1, "pending");
            updateStepStatus(2, "pending");
            updateStepStatus(3, "pending");
            updateStepStatus(4, "pending");
            
            const responseContent = document.getElementById("response-content");
            document.getElementById("response-section").classList.remove("hidden");
            responseContent.innerHTML = `<div style="color: #ef4444; font-weight: 600;">Error processing request: ${err.message}</div>`;
        });
}

// -------------------------------------------------------------
// 3. GRAPH PATH HIGHLIGHTING (THE PATH TRAVERSAL VISUALIZER)
// -------------------------------------------------------------
function highlightTraversalPath(highlightedNodeIds) {
    if (!nodesDataSet || !edgesDataSet || !networkInstance) return;
    
    hideNodeDetailsSidebar();
    
    const hasHighlights = highlightedNodeIds && highlightedNodeIds.length > 0;
    
    if (hasHighlights) {
        // Show ONLY nodes and edges on the path
        const formattedNodesFiltered = originalNodesList
            .filter(node => highlightedNodeIds.includes(node.id))
            .map(node => {
                const style = entityStyles[node.type] || entityStyles.Default;
                const levelMapping = { Supplier: 0, PurchaseOrder: 1, Part: 2, Plant: 2, Product: 3 };
                return {
                    id: node.id,
                    label: `${node.label}\n(${node.type})`,
                    shape: "dot",
                    size: 18, // Clean focused size
                    font: { color: "#f8fafc", size: 10, face: "Inter", bold: true },
                    color: {
                        background: style.background,
                        border: style.border,
                        highlight: { background: style.background, border: style.border }
                    },
                    level: levelMapping[node.type] !== undefined ? levelMapping[node.type] : 2,
                    title: formatTooltip(node.type, node.properties)
                };
            });
            
        const formattedEdgesFiltered = originalEdgesList
            .filter(edge => highlightedNodeIds.includes(edge.from) && highlightedNodeIds.includes(edge.to))
            .map((edge, index) => {
                return {
                    id: `edge-highlight-${index}`,
                    from: edge.from,
                    to: edge.to,
                    label: edge.label,
                    arrows: "to",
                    font: { color: "#f472b6", size: 10, align: "horizontal", face: "Inter" },
                    color: { color: "#ec4899", highlight: "#ec4899" }, // Thick hot pink path
                    width: 3.5
                };
            });
            
        // Re-populate DataSets
        nodesDataSet.clear();
        edgesDataSet.clear();
        
        nodesDataSet.add(formattedNodesFiltered);
        edgesDataSet.add(formattedEdgesFiltered);
        
        // Stabilize physics simulation and pan/zoom screen
        setTimeout(() => {
            networkInstance.stabilize();
            networkInstance.fit({
                animation: { duration: 800, easingFunction: "easeInOutQuad" }
            });
        }, 200);
    } else {
        restoreFullGraph();
    }
}

function restoreFullGraph() {
    if (!nodesDataSet || !edgesDataSet || !networkInstance) return;
    
    nodesDataSet.clear();
    edgesDataSet.clear();
    
    const formattedNodes = originalNodesList.map(node => {
        const style = entityStyles[node.type] || entityStyles.Default;
        const levelMapping = { Supplier: 0, PurchaseOrder: 1, Part: 2, Plant: 2, Product: 3 };
        return {
            id: node.id,
            label: `${node.label}\n(${node.type})`,
            shape: "dot",
            size: 15,
            font: { color: "#f8fafc", size: 10, face: "Inter" },
            color: {
                background: style.background,
                border: style.border,
                highlight: { background: style.background, border: style.border }
            },
            level: levelMapping[node.type] !== undefined ? levelMapping[node.type] : 2,
            title: formatTooltip(node.type, node.properties)
        };
    });
    
    const formattedEdges = originalEdgesList.map((edge, index) => {
        return {
            id: `edge-${index}`,
            from: edge.from,
            to: edge.to,
            label: edge.label,
            arrows: "to",
            font: { color: "#64748b", size: 8, align: "horizontal", face: "Inter" },
            color: { color: "rgba(255, 255, 255, 0.15)", highlight: "#94a3b8" },
            width: 1
        };
    });
    
    nodesDataSet.add(formattedNodes);
    edgesDataSet.add(formattedEdges);
    
    setTimeout(() => {
        networkInstance.stabilize();
        networkInstance.fit({
            animation: { duration: 800, easingFunction: "easeInOutQuad" }
        });
    }, 200);
}

// Utility to get colors directly from CSS variables
function varColor(varName) {
    return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
}

// -------------------------------------------------------------
// 4. RENDER CONSOLE RESULTS, HOPS, & CITATIONS
// -------------------------------------------------------------
function renderResults(data) {
    // A. Show Cypher Query Box
    document.getElementById("code-section").classList.remove("hidden");
    document.getElementById("cypher-output").textContent = data.cypher_query;
    
    // B. Show Raw Database Query Results (Pretty-Printed)
    document.getElementById("results-output").textContent = JSON.stringify(data.raw_results, null, 2);
    
    // B. Show Traversal Hops (Visual flow)
    const hopsContainer = document.getElementById("traversal-hops");
    hopsContainer.innerHTML = "";
    
    if (data.traversal_steps && data.traversal_steps.length > 0) {
        data.traversal_steps.forEach(step => {
            const hopCard = document.createElement("div");
            hopCard.className = "hop-card";
            hopCard.innerHTML = `
                <span class="hop-number">#${step.step_number}</span>
                <div class="hop-flow">
                    <span style="color: ${getEntityColor(step.source_type)}">${step.source_type}</span>
                    <span class="hop-arrow">➔</span>
                    <span style="color: ${getEntityColor(step.target_type)}">${step.target_type}</span>
                </div>
                <span class="hop-desc">${step.description}</span>
            `;
            hopsContainer.appendChild(hopCard);
        });
    } else {
        hopsContainer.innerHTML = `<div class="step-desc" style="padding-left:14px">Direct lookup. No hops required.</div>`;
    }
    
    // C. Show Conversational Answer
    document.getElementById("response-section").classList.remove("hidden");
    // Simple parser converting **text** to HTML bold and newlines to breaks
    const htmlText = formatMarkdownToHTML(data.response_text);
    document.getElementById("response-content").innerHTML = htmlText;
    
    // D. Show Citations Audit Cards
    const citationsContainer = document.getElementById("citations-list");
    citationsContainer.innerHTML = "";
    
    if (data.citations && data.citations.length > 0) {
        document.getElementById("citations-section").classList.remove("hidden");
        
        data.citations.forEach(c => {
            const card = document.createElement("div");
            card.className = "citation-card";
            card.innerHTML = `
                <div class="citation-header">
                    <span class="citation-po">${c.source_po !== "N/A" ? c.source_po : "General Record"}</span>
                    <span class="step-desc" style="color: var(--color-product)">${c.product !== "N/A" ? c.product : "All Products"}</span>
                </div>
                <div class="citation-desc">${c.description}</div>
                <div class="citation-meta">
                    <div class="meta-item">Supplier: <span class="meta-value">${c.supplier}</span></div>
                    <div class="meta-item">Component: <span class="meta-value">${c.part}</span></div>
                    <div class="meta-item">Plant: <span class="meta-value">${c.plant}</span></div>
                </div>
            `;
            citationsContainer.appendChild(card);
        });
    } else {
        document.getElementById("citations-section").classList.add("hidden");
    }
}

function getEntityColor(type) {
    const style = entityStyles[type];
    return style ? style.background : "#94a3b8";
}

function formatMarkdownToHTML(text) {
    if (!text) return "";
    
    // Normalize squashed text
    let formattedText = text;
    formattedText = formattedText.replace(/ \*( |)/g, "\n* ");
    
    // Line-by-line compiler for markdown to clean HTML
    const lines = formattedText.split("\n");
    let html = "";
    let inList = false;
    let inTable = false;
    let isHeaderRow = false;
    
    for (let line of lines) {
        line = line.trim();
        if (!line) {
            if (inList) { html += "</ul>"; inList = false; }
            if (inTable) { html += "</table>"; inTable = false; }
            continue;
        }
        
        // Table Parsing
        if (line.startsWith("|")) {
            if (inList) { html += "</ul>"; inList = false; }
            if (!inTable) {
                html += "<table>";
                inTable = true;
                isHeaderRow = true;
            }
            
            // Extract cell contents between pipes
            const cells = line.split("|").map(c => c.trim()).filter((c, idx, arr) => idx > 0 && idx < arr.length - 1);
            
            // Skip separator line e.g. |---|---|
            if (cells.every(c => c.match(/^:-*-?:*$/) || c.match(/^-+$/))) {
                continue;
            }
            
            html += "<tr>";
            for (let cell of cells) {
                let formattedCell = cell
                    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                    .replace(/\*(.*?)\*/g, "<em>$1</em>");
                if (isHeaderRow) {
                    html += `<th>${formattedCell}</th>`;
                } else {
                    html += `<td>${formattedCell}</td>`;
                }
            }
            html += "</tr>";
            isHeaderRow = false;
        }
        // Headers
        else if (line.startsWith("### ")) {
            if (inList) { html += "</ul>"; inList = false; }
            if (inTable) { html += "</table>"; inTable = false; }
            html += `<h3>${line.substring(4).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")}</h3>`;
        } else if (line.startsWith("## ")) {
            if (inList) { html += "</ul>"; inList = false; }
            if (inTable) { html += "</table>"; inTable = false; }
            html += `<h2>${line.substring(3).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")}</h2>`;
        } else if (line.startsWith("# ")) {
            if (inList) { html += "</ul>"; inList = false; }
            if (inTable) { html += "</table>"; inTable = false; }
            html += `<h1>${line.substring(2).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")}</h1>`;
        }
        // Bullet Lists
        else if (line.startsWith("* ") || line.startsWith("- ")) {
            if (inTable) { html += "</table>"; inTable = false; }
            if (!inList) {
                html += "<ul>";
                inList = true;
            }
            let formattedItem = line.substring(2)
                .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                .replace(/\*(.*?)\*/g, "<em>$1</em>");
            html += `<li>${formattedItem}</li>`;
        }
        // Paragraphs
        else {
            if (inList) { html += "</ul>"; inList = false; }
            if (inTable) { html += "</table>"; inTable = false; }
            // Parse inline bold/italics
            let formattedLine = line
                .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                .replace(/\*(.*?)\*/g, "<em>$1</em>");
            html += `<p>${formattedLine}</p>`;
        }
    }
    
    if (inList) html += "</ul>";
    if (inTable) html += "</table>";
    
    return html;
}
