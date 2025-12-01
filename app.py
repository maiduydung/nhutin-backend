"""
Gradio-based Inventory Dashboard with Chat Assistant.
Provides data visualization and LLM-powered insights for inventory data.
"""

import os
import gradio as gr
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from openai import OpenAI
from services.analytics import Analytics
from config import get_config, logger

# Initialize OpenAI client (uses OPENAI_API_KEY from environment)
OPENAI_API_KEY = get_config("OPENAI_API_KEY")
openaiClient = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# =============================================================================
# STYLING & FORMATTING
# =============================================================================

# Beautiful color palette (Tailwind-inspired)
COLORS = {
    "primary": "#3B82F6",      # Blue
    "success": "#10B981",      # Emerald
    "warning": "#F59E0B",      # Amber
    "danger": "#EF4444",       # Red
    "purple": "#8B5CF6",       # Violet
    "pink": "#EC4899",         # Pink
    "cyan": "#06B6D4",         # Cyan
    "orange": "#F97316",       # Orange
    "lime": "#84CC16",         # Lime
    "indigo": "#6366F1",       # Indigo
    "teal": "#14B8A6",         # Teal
    "rose": "#F43F5E",         # Rose
}

# Color sequence for charts
CHART_COLORS = [
    "#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899",
    "#06B6D4", "#F97316", "#84CC16", "#6366F1", "#14B8A6",
    "#EF4444", "#F43F5E", "#22D3EE", "#A3E635", "#C084FC"
]

# Type label mapping (snake_case -> Nice Label)
TYPE_LABELS = {
    "walking_floor_ksd": "Sàn KSD",
    "walking_floor_r2dx": "Sàn R2DX", 
    "walking_floor_kmd": "Sàn KMD",
    "aluminum": "Nhôm",
    "burning_fuel": "Nhiên liệu",
    "container": "Container",
    "steel_box": "Thép hộp",
    "steel_plate": "Thép tấm",
    "steel_pipe": "Thép ống",
    "steel_u": "Thép U",
    "steel_i": "Thép I",
    "steel_square": "Thép vuông",
    "stainless_steel": "Inox",
    "galvanized_sheet": "Tôn mạ kẽm",
    "hydraulic_pump": "Bơm thủy lực",
    "controller": "Bộ điều khiển",
}


def prettifyTypeName(typeName: str) -> str:
    """Convert snake_case type to pretty label."""
    if typeName in TYPE_LABELS:
        return TYPE_LABELS[typeName]
    # Fallback: convert snake_case to Title Case
    return typeName.replace("_", " ").title()


def formatCurrency(value: int) -> str:
    """Format number as Vietnamese currency."""
    if value is None:
        return "0 ₫"
    return f"{value:,.0f} ₫".replace(",", ".")


def formatCurrencyShort(value: float) -> str:
    """Format large numbers with B/M suffix."""
    if value is None or value == 0:
        return "0"
    if abs(value) >= 1_000_000_000:
        return f"{value/1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value/1_000:.0f}K"
    return f"{value:.0f}"


def formatNumber(value: int) -> str:
    """Format number with thousand separators."""
    if value is None:
        return "0"
    return f"{value:,.0f}".replace(",", ".")


def getSummaryMarkdown() -> str:
    """Generate summary statistics as markdown."""
    try:
        stats = Analytics.getSummaryStats()
        
        snapshot = stats.get("latestSnapshot", {})
        allTime = stats.get("allTime", {})
        
        md = f"""
## 📊 Tổng quan Tồn kho

### Cập nhật gần nhất ({snapshot.get('date', 'N/A')})
| Chỉ số | Giá trị |
|--------|---------|
| 📦 Tổng mặt hàng | {formatNumber(snapshot.get('itemsCount', 0))} |
| 🔢 Tổng số lượng | {formatNumber(snapshot.get('totalQuantity', 0))} |
| 💰 Tổng giá trị | {formatCurrency(snapshot.get('totalValue', 0))} |

### Hoạt động toàn thời gian
| Chỉ số | Số lượng | Giá trị |
|--------|----------|---------|
| 📥 Tổng nhập | {formatNumber(allTime.get('totalImported', 0))} | {formatCurrency(allTime.get('totalImportedValue', 0))} |
| 📤 Tổng xuất | {formatNumber(allTime.get('totalExported', 0))} | {formatCurrency(allTime.get('totalExportedValue', 0))} |

### Phân loại hàng hóa
"""
        itemsByType = stats.get("itemsByType", {})
        for itemType, count in itemsByType.items():
            prettyName = prettifyTypeName(itemType)
            md += f"- **{prettyName}**: {count} mặt hàng\n"
        
        return md
    
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return f"❌ Lỗi tải dữ liệu: {str(e)}"


def createTypeDistributionChart():
    """Create clean, elegant donut chart of inventory by type."""
    try:
        df = Analytics.getItemTypeDistribution()
        if df.empty:
            return None
        
        df = df.copy()
        df["pretty_type"] = df["type"].apply(prettifyTypeName)
        df = df.sort_values("total_value", ascending=False)
        
        # Keep top 5, group rest as "Khác"
        if len(df) > 5:
            topDf = df.head(5).copy()
            otherValue = df.iloc[5:]["total_value"].sum()
            otherRow = pd.DataFrame({
                "type": ["other"],
                "pretty_type": ["Khác"],
                "total_value": [otherValue],
                "item_count": [df.iloc[5:]["item_count"].sum()],
                "total_quantity": [df.iloc[5:]["total_quantity"].sum()]
            })
            df = pd.concat([topDf, otherRow], ignore_index=True)
        
        # Elegant color palette
        elegantColors = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#94A3B8"]
        
        fig = go.Figure(data=[go.Pie(
            labels=df["pretty_type"],
            values=df["total_value"],
            hole=0.6,
            textinfo='percent',
            textposition='inside',
            textfont=dict(size=13, color="white", family="Inter, sans-serif"),
            marker=dict(
                colors=elegantColors[:len(df)],
                line=dict(color='white', width=3)
            ),
            hovertemplate="<b>%{label}</b><br>" +
                         "Giá trị: %{value:,.0f} ₫<br>" +
                         "Tỷ lệ: %{percent}<extra></extra>",
            sort=False
        )])
        
        fig.update_layout(
            title=dict(
                text="<b>Phân bổ theo loại hàng</b>",
                font=dict(size=15, color="#1F2937", family="Inter, sans-serif"),
                x=0.5,
                xanchor="center"
            ),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.05,
                xanchor="center",
                x=0.5,
                font=dict(size=11, color="#4B5563", family="Inter, sans-serif"),
                itemsizing="constant"
            ),
            paper_bgcolor='white',
            plot_bgcolor='white',
            margin=dict(t=50, b=60, l=10, r=10),
            annotations=[dict(
                text=f"<b>{formatCurrencyShort(df['total_value'].sum())}</b><br><span style='font-size:11px;color:#6B7280'>Tổng</span>",
                x=0.5, y=0.5,
                font=dict(size=18, color="#1F2937", family="Inter, sans-serif"),
                showarrow=False
            )],
            height=320
        )
        return fig
    
    except Exception as e:
        logger.error(f"Error creating type chart: {e}")
        return None


def createTopItemsChart(metric: str = "value"):
    """Create slim, elegant horizontal bar chart of top items."""
    try:
        df = Analytics.getTopItems(6, metric)  # Top 6 for cleaner look
        if df.empty:
            return None
        
        df = df.copy()
        
        # Shorten long names more aggressively
        df["short_name"] = df["name"].apply(
            lambda x: (x[:22] + "...") if len(str(x)) > 25 else x
        )
        
        yColumn = "final_value" if metric == "value" else "final_quantity"
        title = "Top mặt hàng theo giá trị"
        
        # Sort ascending for plotly horizontal bar (top value at top)
        df = df.sort_values(yColumn, ascending=True)
        
        # Gradient blue colors (lighter to darker)
        nItems = len(df)
        blueGradient = [f"rgba(59, 130, 246, {0.45 + 0.55 * i / nItems})" for i in range(nItems)]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            y=df["short_name"],
            x=df[yColumn],
            orientation='h',
            marker=dict(
                color=blueGradient,
                line=dict(width=0)
            ),
            text=df[yColumn].apply(lambda v: formatCurrencyShort(v)),
            textposition='outside',
            textfont=dict(size=10, color="#6B7280", family="Inter, sans-serif"),
            hovertemplate="<b>%{y}</b><br>Giá trị: %{x:,.0f} ₫<extra></extra>",
            width=0.55
        ))
        
        fig.update_layout(
            title=dict(
                text=f"<b>{title}</b>",
                font=dict(size=14, color="#1F2937", family="Inter, sans-serif"),
                x=0.5,
                xanchor="center"
            ),
            showlegend=False,
            paper_bgcolor='white',
            plot_bgcolor='white',
            xaxis=dict(
                title="",
                showgrid=True,
                gridcolor='#F3F4F6',
                zeroline=False,
                tickfont=dict(size=9, color="#9CA3AF"),
                tickformat=".2s"
            ),
            yaxis=dict(
                title="",
                showgrid=False,
                tickfont=dict(size=10, color="#374151", family="Inter, sans-serif"),
                ticklabelposition="outside"
            ),
            margin=dict(t=45, b=25, l=155, r=55),
            height=220,
            bargap=0.45
        )
        return fig
    
    except Exception as e:
        logger.error(f"Error creating top items chart: {e}")
        return None


def createMovementChart():
    """Create elegant horizontal bar chart for imports vs exports."""
    try:
        df = Analytics.getMovementAnalysis()
        if df.empty:
            return None
        
        df = df.copy()
        
        # Filter items with activity and take top 4 for cleaner look
        df = df[(df['imported_value'] > 0) | (df['exported_value'] > 0)]
        df = df.head(4)
        
        if df.empty:
            return None
        
        # Shorten names
        df["short_name"] = df["name"].apply(
            lambda x: (x[:14] + "...") if len(str(x)) > 17 else x
        )
        
        fig = go.Figure()
        
        # Horizontal slim bars for import
        fig.add_trace(go.Bar(
            name='Nhập kho',
            y=df['short_name'],
            x=df['imported_value'],
            orientation='h',
            marker=dict(
                color='rgba(16, 185, 129, 0.85)',
                line=dict(width=0)
            ),
            text=df['imported_value'].apply(formatCurrencyShort),
            textposition='outside',
            textfont=dict(size=10, color="#059669", family="Inter, sans-serif"),
            hovertemplate="<b>%{y}</b><br>Nhập: %{x:,.0f} ₫<extra></extra>",
            width=0.4
        ))
        
        # Horizontal slim bars for export
        fig.add_trace(go.Bar(
            name='Xuất kho',
            y=df['short_name'],
            x=df['exported_value'],
            orientation='h',
            marker=dict(
                color='rgba(248, 113, 113, 0.85)',
                line=dict(width=0)
            ),
            text=df['exported_value'].apply(formatCurrencyShort),
            textposition='outside',
            textfont=dict(size=10, color="#EF4444", family="Inter, sans-serif"),
            hovertemplate="<b>%{y}</b><br>Xuất: %{x:,.0f} ₫<extra></extra>",
            width=0.4
        ))
        
        fig.update_layout(
            title=dict(
                text="<b>Hoạt động Nhập/Xuất</b>",
                font=dict(size=14, color="#1F2937", family="Inter, sans-serif"),
                x=0.5,
                xanchor="center"
            ),
            barmode='group',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
                font=dict(size=10, color="#6B7280", family="Inter, sans-serif"),
                itemsizing="constant"
            ),
            paper_bgcolor='white',
            plot_bgcolor='white',
            xaxis=dict(
                title="",
                showgrid=True,
                gridcolor='#F3F4F6',
                zeroline=False,
                tickfont=dict(size=9, color="#9CA3AF"),
                tickformat=".2s"
            ),
            yaxis=dict(
                title="",
                tickfont=dict(size=10, color="#374151", family="Inter, sans-serif"),
                showgrid=False
            ),
            margin=dict(t=55, b=25, l=110, r=50),
            height=180,
            bargap=0.5,
            bargroupgap=0.15
        )
        return fig
    
    except Exception as e:
        logger.error(f"Error creating movement chart: {e}")
        return None


def createInventoryTrendChart():
    """Create elegant, minimal trend chart."""
    try:
        df = Analytics.getInventoryTrends(30)  # 30 days for cleaner view
        if df.empty:
            return None
        
        fig = go.Figure()
        
        # Clean area chart for total value
        fig.add_trace(
            go.Scatter(
                x=df['record_date'],
                y=df['total_value'],
                name='Tổng giá trị',
                mode='lines',
                line=dict(color='#3B82F6', width=2.5),
                fill='tozeroy',
                fillcolor='rgba(59, 130, 246, 0.08)',
                hovertemplate="<b>%{x|%d/%m}</b><br>%{y:,.0f} ₫<extra></extra>"
            )
        )
        
        # Add subtle markers for import activity
        importDf = df[df['import_value'] > 0]
        if not importDf.empty:
            fig.add_trace(
                go.Scatter(
                    x=importDf['record_date'],
                    y=importDf['total_value'],
                    name='Có nhập kho',
                    mode='markers',
                    marker=dict(color='#10B981', size=8, symbol='circle'),
                    hovertemplate="<b>%{x|%d/%m}</b><br>Nhập: %{customdata:,.0f} ₫<extra></extra>",
                    customdata=importDf['import_value']
                )
            )
        
        fig.update_layout(
            title=dict(
                text="<b>Xu hướng tồn kho</b>",
                font=dict(size=15, color="#1F2937", family="Inter, sans-serif"),
                x=0.5,
                xanchor="center"
            ),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=10, color="#6B7280", family="Inter, sans-serif"),
                itemsizing="constant"
            ),
            paper_bgcolor='white',
            plot_bgcolor='white',
            hovermode='x',
            margin=dict(t=60, b=40, l=60, r=30),
            height=260
        )
        
        fig.update_xaxes(
            showgrid=False,
            tickfont=dict(size=9, color="#9CA3AF", family="Inter, sans-serif"),
            tickformat="%d/%m"
        )
        
        fig.update_yaxes(
            title="",
            showgrid=True,
            gridcolor='#F3F4F6',
            tickfont=dict(size=9, color="#9CA3AF"),
            tickformat=".2s"
        )
        
        return fig
    
    except Exception as e:
        logger.error(f"Error creating trend chart: {e}")
        return None


def getDataContext() -> str:
    """Get current data context for LLM."""
    try:
        stats = Analytics.getSummaryStats()
        topItems = Analytics.getTopItems(5)
        typeDistribution = Analytics.getItemTypeDistribution()
        
        context = f"""
Current Inventory Data Context:
- Total unique items: {stats.get('totalItems', 0)}
- Latest snapshot date: {stats.get('latestSnapshot', {}).get('date', 'N/A')}
- Total inventory value: {formatCurrency(stats.get('latestSnapshot', {}).get('totalValue', 0))}
- Total inventory quantity: {formatNumber(stats.get('latestSnapshot', {}).get('totalQuantity', 0))}

Item Types Distribution:
{typeDistribution.to_string() if not typeDistribution.empty else 'No data'}

Top 5 Items by Value:
{topItems.to_string() if not topItems.empty else 'No data'}

All-Time Activity:
- Total imported: {formatNumber(stats.get('allTime', {}).get('totalImported', 0))} units worth {formatCurrency(stats.get('allTime', {}).get('totalImportedValue', 0))}
- Total exported: {formatNumber(stats.get('allTime', {}).get('totalExported', 0))} units worth {formatCurrency(stats.get('allTime', {}).get('totalExportedValue', 0))}
"""
        return context
    except Exception as e:
        return f"Error loading data context: {str(e)}"


def chatWithInventory(message: str, history: list) -> str:
    """
    Chat function that uses LLM to answer questions about inventory.
    Falls back to rule-based responses if no API key.
    """
    if not message.strip():
        return "Please enter a question about the inventory."
    
    dataContext = getDataContext()
    
    # If OpenAI is available, use it
    if openaiClient:
        try:
            systemPrompt = f"""You are a helpful inventory analyst assistant for a Vietnamese business.
You have access to the following inventory data:

{dataContext}

Answer questions about the inventory data concisely and helpfully.
Use Vietnamese dong (₫) for currency values.
If asked about specific items, use the search functionality.
Provide insights and recommendations when appropriate.
Respond in the same language as the user's question."""

            messages = [{"role": "system", "content": systemPrompt}]
            
            # Add conversation history
            for h in history:
                messages.append({"role": "user", "content": h[0]})
                if h[1]:
                    messages.append({"role": "assistant", "content": h[1]})
            
            messages.append({"role": "user", "content": message})
            
            response = openaiClient.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return f"❌ LLM Error: {str(e)}\n\nFalling back to data summary:\n{dataContext}"
    
    # Fallback: Return data context
    return f"""🤖 **No LLM configured** (set OPENAI_API_KEY to enable AI chat)

Here's the current inventory summary:

{dataContext}

**To enable AI-powered chat:**
1. Get an OpenAI API key from https://platform.openai.com
2. Add `OPENAI_API_KEY=your-key` to local.settings.json or environment
3. Restart the application"""


def searchItemsUI(query: str) -> pd.DataFrame:
    """Search items and return results as DataFrame."""
    if not query.strip():
        return pd.DataFrame()
    
    try:
        df = Analytics.searchItems(query)
        return df
    except Exception as e:
        logger.error(f"Search error: {e}")
        return pd.DataFrame()


def getAllItemsDataframe() -> pd.DataFrame:
    """Get all items with latest inventory data."""
    try:
        return Analytics.getAllItemsWithLatestInventory()
    except Exception as e:
        logger.error(f"Error loading items: {e}")
        return pd.DataFrame()


def refreshDashboard():
    """Refresh all dashboard components."""
    return (
        getSummaryMarkdown(),
        createTypeDistributionChart(),
        createTopItemsChart("value"),
        createMovementChart(),
        createInventoryTrendChart()
    )


# Build the Gradio interface
def createApp():
    """Create and configure the Gradio app."""
    
    with gr.Blocks(
        title="Nhu Tin Inventory Dashboard",
        fill_height=True
    ) as app:
        
        # Header
        gr.Markdown("""
        # 🏭 Nhu Tin Inventory Dashboard
        **Phân tích tồn kho thời gian thực và trợ lý AI**
        """)
        
        with gr.Tabs() as tabs:
            # Overview Tab
            with gr.TabItem("📊 Tổng quan", id=0):
                with gr.Row():
                    with gr.Column(scale=1):
                        summaryMd = gr.Markdown(value=getSummaryMarkdown, every=30)
                    
                    with gr.Column(scale=2):
                        typeChart = gr.Plot(value=createTypeDistributionChart, label="Phân bổ")
                
                with gr.Row():
                    topItemsChart = gr.Plot(value=createTopItemsChart, label="Top mặt hàng")
                
                with gr.Row():
                    movementChart = gr.Plot(value=createMovementChart, label="Nhập/Xuất kho")
                
                with gr.Row():
                    trendChart = gr.Plot(value=createInventoryTrendChart, label="Xu hướng")
                
                with gr.Row():
                    refreshBtn = gr.Button("🔄 Làm mới", variant="primary")
                    refreshBtn.click(
                        fn=refreshDashboard,
                        outputs=[summaryMd, typeChart, topItemsChart, movementChart, trendChart]
                    )
            
            # Chat Tab
            with gr.TabItem("💬 Trợ lý AI", id=1):
                gr.Markdown("""
                ### Đặt câu hỏi về kho hàng
                Trợ lý AI có thể giúp bạn hiểu dữ liệu tồn kho, xác định xu hướng và đưa ra insights.
                """)
                
                chatbot = gr.Chatbot(
                    height=500,
                    placeholder="Ask me anything about your inventory...",
                    show_label=False
                )
                
                with gr.Row():
                    chatInput = gr.Textbox(
                        placeholder="e.g., What are my top selling items? / Tổng giá trị tồn kho là bao nhiêu?",
                        show_label=False,
                        scale=9
                    )
                    sendBtn = gr.Button("Send", variant="primary", scale=1)
                
                def respond(message, history):
                    if not message.strip():
                        return "", history
                    
                    # Convert history from new format (list of dicts) to old format (list of tuples)
                    oldFormatHistory = []
                    userMsg = ""
                    for msg in history:
                        if isinstance(msg, dict):
                            if msg.get("role") == "user":
                                userMsg = msg.get("content", "")
                            elif msg.get("role") == "assistant":
                                oldFormatHistory.append((userMsg, msg.get("content", "")))
                    
                    response = chatWithInventory(message, oldFormatHistory)
                    # Return in new message format (Gradio 6.0)
                    history.append({"role": "user", "content": message})
                    history.append({"role": "assistant", "content": response})
                    return "", history
                
                chatInput.submit(respond, [chatInput, chatbot], [chatInput, chatbot])
                sendBtn.click(respond, [chatInput, chatbot], [chatInput, chatbot])
                
                gr.Examples(
                    examples=[
                        "What is the total inventory value?",
                        "Tổng giá trị hàng tồn kho là bao nhiêu?",
                        "Which item types have the highest value?",
                        "Show me the import vs export summary",
                        "What are the top 5 items by quantity?"
                    ],
                    inputs=chatInput
                )
            
            # Search Tab
            with gr.TabItem("🔍 Tìm kiếm", id=2):
                gr.Markdown("### Tìm kiếm mặt hàng theo mã hoặc tên")
                
                with gr.Row():
                    searchInput = gr.Textbox(
                        placeholder="Nhập mã hoặc tên mặt hàng...",
                        show_label=False,
                        scale=4
                    )
                    searchBtn = gr.Button("🔍 Tìm", variant="primary", scale=1)
                
                searchResults = gr.Dataframe(
                    headers=["code", "name", "type", "unit", "final_quantity", "final_value", "record_date"],
                    label="Kết quả tìm kiếm",
                    interactive=False
                )
                
                searchBtn.click(fn=searchItemsUI, inputs=searchInput, outputs=searchResults)
                searchInput.submit(fn=searchItemsUI, inputs=searchInput, outputs=searchResults)
            
            # Data Table Tab
            with gr.TabItem("📋 Tất cả", id=3):
                gr.Markdown("### Danh sách đầy đủ tất cả mặt hàng")
                
                with gr.Row():
                    loadDataBtn = gr.Button("📥 Tải danh sách", variant="primary")
                
                allItemsTable = gr.Dataframe(
                    label="Tất cả mặt hàng tồn kho",
                    interactive=False,
                    wrap=True
                )
                
                loadDataBtn.click(fn=getAllItemsDataframe, outputs=allItemsTable)
        
        # Footer
        gr.Markdown("""
        ---
        *Xây dựng với Gradio & Plotly | Hệ thống quản lý kho Nhu Tín*
        """)
    
    return app


# Main entry point
if __name__ == "__main__":
    app = createApp()
    logger.info("🚀 Starting Nhu Tin Inventory Dashboard...")
    
    # Force light theme with dark text
    lightThemeCss = """
    :root, .dark, body, html {
        --background-fill-primary: #ffffff !important;
        --background-fill-secondary: #f9fafb !important;
        --block-background-fill: #ffffff !important;
        --body-background-fill: #ffffff !important;
        --color-background-primary: #ffffff !important;
        --color-background-secondary: #f9fafb !important;
        
        /* Force dark text colors */
        --body-text-color: #111827 !important;
        --block-title-text-color: #111827 !important;
        --block-label-text-color: #1f2937 !important;
        --input-text-color: #111827 !important;
        --color-text-body: #111827 !important;
        --text-color: #111827 !important;
        
        --neutral-50: #f9fafb !important;
        --neutral-100: #f3f4f6 !important;
        --neutral-200: #e5e7eb !important;
        --neutral-700: #374151 !important;
        --neutral-800: #1f2937 !important;
        --neutral-900: #111827 !important;
        --neutral-950: #030712 !important;
    }
    
    body, .gradio-container, .main, .contain {
        background: #ffffff !important;
        color: #111827 !important;
    }
    
    /* Force all text to be dark */
    h1, h2, h3, h4, h5, h6, p, span, div, label, td, th, li, strong, em, a {
        color: #111827 !important;
    }
    
    /* Keep buttons readable */
    button.primary {
        color: white !important;
    }
    
    /* Table styling */
    table, th, td {
        color: #111827 !important;
    }
    
    /* Input fields */
    input, textarea {
        color: #111827 !important;
        background: #ffffff !important;
    }
    
    /* Placeholder text */
    input::placeholder, textarea::placeholder {
        color: #6b7280 !important;
    }
    
    /* Chatbot fix */
    .chatbot .message {
        color: #111827 !important;
    }
    """
    
    lightThemeJs = """
    function() {
        document.body.classList.remove('dark');
        document.documentElement.classList.remove('dark');
        document.documentElement.setAttribute('data-theme', 'light');
    }
    """
    
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme="soft",
        css=lightThemeCss,
        js=lightThemeJs
    )

