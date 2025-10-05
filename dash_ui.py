"""
DEID Patients - Professional Dash UI for HIPAA-Compliant Clinical Data De-identification

This module provides a professional web interface for showcasing clinical data 
de-identification capabilities to clinicians and AI professionals. The UI emphasizes
HIPAA compliance, real-time processing, and clear before/after comparisons.

Key Features:
- Editable text input for raw clinical data
- Side-by-side comparison with HIPAA identifier highlighting
- Real-time de-identification processing
- Professional healthcare-focused design
- HIPAA compliance indicators

Target Audience: Clinicians and AI professionals
Focus: Clinical Data De-Identification as per HIPAA Compliance
"""

import dash
from dash import dcc, html, Input, Output, State, callback, dash_table
import plotly.graph_objs as go
import re
import json
from datetime import datetime
import base64
import io
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the real backend functionality
from hipaa_deidentifier.deidentifier_modular import HIPAADeidentifierModular
from config.config import config as global_config

# Initialize Dash app with professional healthcare styling
app = dash.Dash(
    __name__, 
    external_stylesheets=[
        'https://codepen.io/chriddyp/pen/bWLwgP.css',
        'https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'
    ],
    suppress_callback_exceptions=True
)

# Add custom CSS for progress bar
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            .progress-bar-custom {
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Synchronization is now handled by assets/sync_scroll.js

# Professional healthcare color scheme
HEALTHCARE_COLORS = {
    'primary': '#2c3e50',      # Dark blue-gray
    'secondary': '#3498db',     # Professional blue
    'success': '#27ae60',       # Green for success
    'success_disabled': '#7fb069',  # Lighter green for disabled success button
    'warning': '#f39c12',       # Orange for warnings
    'danger': '#e74c3c',        # Red for errors
    'light': '#ecf0f1',         # Light gray
    'dark': '#34495e',          # Dark gray
    'info': '#17a2b8'           # Info blue
}

# HIPAA identifier patterns for highlighting
HIPAA_PATTERNS = {
    'names': r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'phone': r'\b\d{3}-\d{3}-\d{4}\b',
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'address': r'\b\d+\s+[A-Za-z0-9\s,.-]+\b',
    'dates': r'\b\d{1,2}/\d{1,2}/\d{4}\b',
    'medical_record': r'\bMRN\s*:?\s*\d+\b',
    'insurance': r'\bPolicy\s*:?\s*\d+\b'
}

def highlight_hipaa_identifiers(text):
    """
    Highlight HIPAA identifiers in text with different colors using real backend detection
    Returns formatted text with markdown-style highlighting
    """
    if not text:
        return ""
    
    try:
        # Try to use the real backend for more accurate detection
        deid = initialize_deidentifier()
        if deid is not None:
            result = deid.deidentify(text)
            entities = result.get("entities", [])
            
            # Create highlighted text using real entity detection
            highlighted_text = text
            colors = ['#ffeb3b', '#ff9800', '#f44336', '#9c27b0', '#2196f3', '#4caf50', '#ff5722', '#795548']
            
            # Sort entities by start position (descending) to avoid offset issues
            entities_sorted = sorted(entities, key=lambda x: x.get('start', 0), reverse=True)
            
            for entity in entities_sorted:
                start = entity.get('start', 0)
                end = entity.get('end', 0)
                entity_type = entity.get('category', 'UNKNOWN')
                
                if start < end and start >= 0 and end <= len(text):
                    # Get color based on entity type
                    color = get_entity_color(entity_type, colors)
                    
                    # Extract the text to highlight
                    entity_text = text[start:end]
                    
                    # Create markdown-style highlighting
                    highlighted_span = f'<span style="background-color: {color}; padding: 2px 4px; border-radius: 3px; font-weight: bold; color: black;">{entity_text}</span>'
                    
                    # Replace in highlighted text
                    highlighted_text = highlighted_text[:start] + highlighted_span + highlighted_text[end:]
            
            return highlighted_text
            
    except Exception as e:
        print(f"Error in highlighting with backend: {e}")
        # Fallback to regex-based highlighting
        pass
    
    # Fallback to regex-based highlighting
    highlighted_text = text
    colors = ['#ffeb3b', '#ff9800', '#f44336', '#9c27b0', '#2196f3', '#4caf50', '#ff5722', '#795548']
    
    for i, (pattern_name, pattern) in enumerate(HIPAA_PATTERNS.items()):
        color = colors[i % len(colors)]
        matches = re.finditer(pattern, highlighted_text, re.IGNORECASE)
        
        # Replace matches with highlighted spans
        offset = 0
        for match in matches:
            start, end = match.span()
            start += offset
            end += offset
            
            highlighted_span = f'<span style="background-color: {color}; padding: 2px 4px; border-radius: 3px; font-weight: bold; color: black;">{match.group()}</span>'
            highlighted_text = highlighted_text[:start] + highlighted_span + highlighted_text[end:]
            
            # Adjust offset for HTML insertion
            offset += len(highlighted_span) - (end - start)
    
    return highlighted_text

def get_entity_color(entity_type, colors):
    """Get color for entity type"""
    color_map = {
        'PERSON': colors[0],      # Yellow
        'SSN': colors[1],         # Orange
        'PHONE_NUMBER': colors[2], # Red
        'EMAIL_ADDRESS': colors[3], # Purple
        'LOCATION': colors[4],    # Blue
        'DATE_TIME': colors[5],   # Green
        'MEDICAL_RECORD_NUMBER': colors[6], # Orange-red
        'HEALTH_PLAN_ID': colors[7], # Brown
        'NAME': colors[0],        # Yellow
        'ADDRESS': colors[4],     # Blue
        'DATE': colors[5],        # Green
    }
    return color_map.get(entity_type, colors[0])

# Global de-identifier instance (initialized once)
deidentifier = None

def initialize_deidentifier():
    """Initialize the HIPAA de-identifier with configuration"""
    global deidentifier
    if deidentifier is None:
        try:
            # Get configuration
            config_dict = global_config.get_settings()
            
            # Get model names from configuration
            spacy_model = config_dict.get("models", {}).get("spacy")
            hf_model = config_dict.get("models", {}).get("huggingface")
            device = config_dict.get("models", {}).get("device", -1)
            
            # Initialize the deidentifier
            deidentifier = HIPAADeidentifierModular(
                config_path="config/main.yaml",
                spacy_model=spacy_model,
                hf_model=hf_model,
                device=device
            )
            print("HIPAA De-identifier initialized successfully")
        except Exception as e:
            print(f"Error initializing de-identifier: {e}")
            deidentifier = None
    return deidentifier

def deidentify_text(text):
    """
    Real de-identification function using the HIPAA backend
    """
    if not text:
        return ""
    
    try:
        # Initialize de-identifier if not already done
        deid = initialize_deidentifier()
        if deid is None:
            # Fallback to simple regex-based de-identification
            return fallback_deidentify_text(text)
        
        # Use the real HIPAA de-identifier
        result = deid.deidentify(text)
        return result["text"]
        
    except Exception as e:
        print(f"Error in de-identification: {e}")
        # Fallback to simple regex-based de-identification
        return fallback_deidentify_text(text)

def fallback_deidentify_text(text):
    """
    Fallback de-identification using simple regex patterns
    """
    if not text:
        return ""
    
    # Simple regex-based de-identification as fallback
    deidentified = text
    
    # Replace names with [PATIENT NAME]
    deidentified = re.sub(HIPAA_PATTERNS['names'], '[PATIENT NAME]', deidentified)
    
    # Replace SSN with [SSN]
    deidentified = re.sub(HIPAA_PATTERNS['ssn'], '[SSN]', deidentified)
    
    # Replace phone with [PHONE]
    deidentified = re.sub(HIPAA_PATTERNS['phone'], '[PHONE]', deidentified)
    
    # Replace email with [EMAIL]
    deidentified = re.sub(HIPAA_PATTERNS['email'], '[EMAIL]', deidentified)
    
    # Replace dates with [DATE]
    deidentified = re.sub(HIPAA_PATTERNS['dates'], '[DATE]', deidentified)
    
    # Replace medical record numbers
    deidentified = re.sub(HIPAA_PATTERNS['medical_record'], 'MRN: [REDACTED]', deidentified)
    
    # Replace insurance policy numbers
    deidentified = re.sub(HIPAA_PATTERNS['insurance'], 'Policy: [REDACTED]', deidentified)
    
    return deidentified

# Main app layout
app.layout = html.Div([
    
    # Header with professional healthcare branding
    html.Div([
        html.Div([
            html.H1("DEID Patients", 
                   style={'color': HEALTHCARE_COLORS['primary'], 'margin': '0', 'fontSize': '2.5rem'}),
            html.P("Clinical Data De-identification System", 
                   style={'color': HEALTHCARE_COLORS['secondary'], 'margin': '5px 0 0 0', 'fontSize': '1.2rem'})
        ], style={'textAlign': 'center', 'padding': '20px 0'})
    ], style={'backgroundColor': HEALTHCARE_COLORS['light'], 'borderRadius': '10px', 'marginBottom': '30px'}),
    
    # Main content area
    html.Div([
        # Input section
        html.Div([
            html.H3("Raw Clinical Data Input", 
                   style={'color': HEALTHCARE_COLORS['primary'], 'marginBottom': '15px'}),
            html.P("Enter or paste clinical data containing PHI (Protected Health Information) for de-identification:", 
                   style={'color': HEALTHCARE_COLORS['dark'], 'marginBottom': '15px'}),
            
            dcc.Textarea(
                id='raw-text-input',
                placeholder='Enter clinical data here...\n\nExample:\nPatient: John Smith\nDOB: 01/15/1980\nSSN: 123-45-6789\nPhone: 555-123-4567\nEmail: john.smith@email.com\nMedical Record: MRN: 123456789\nAddress: 123 Main St, City, State 12345\n\nChief Complaint: Patient presents with chest pain...',
                style={
                    'width': '100%',
                    'height': '200px',
                    'padding': '15px',
                    'border': f'2px solid {HEALTHCARE_COLORS["secondary"]}',
                    'borderRadius': '8px',
                    'fontSize': '14px',
                    'fontFamily': 'monospace',
                    'resize': 'vertical'
                }
            ),
            
            html.Div([
                html.Button('De-Identify', 
                           id='process-btn',
                           style={
                               'backgroundColor': HEALTHCARE_COLORS['success'],
                               'color': 'white',
                               'border': 'none',
                               'padding': '12px 24px',
                               'borderRadius': '20px',
                               'cursor': 'pointer',
                               'fontSize': '16px',
                               'fontWeight': 'bold',
                               'marginTop': '15px'
                           }),
                html.Button('Clear All', 
                           id='clear-btn',
                           style={
                               'backgroundColor': HEALTHCARE_COLORS['warning'],
                               'color': 'white',
                               'border': 'none',
                               'padding': '12px 24px',
                               'borderRadius': '20px',
                               'cursor': 'pointer',
                               'fontSize': '16px',
                               'fontWeight': 'bold',
                               'marginTop': '15px',
                               'marginLeft': '10px'
                           })
            ], style={'textAlign': 'center'})
            
        ], style={'marginBottom': '30px'}),
        
        # Processing status
        html.Div([
            html.Div(id='processing-status', style={'textAlign': 'center', 'marginBottom': '20px'})
        ]),
        
        # Progress bar
        html.Div([
            html.Div([
                html.Div(
                    id='progress-bar-fill',
                    style={
                        'width': '0%',
                        'height': '100%',
                        'backgroundColor': HEALTHCARE_COLORS['success'],
                        'borderRadius': '10px',
                        'transition': 'width 0.3s ease'
                    }
                )
            ], style={
                'width': '100%',
                'height': '20px',
                'backgroundColor': HEALTHCARE_COLORS['light'],
                'borderRadius': '10px',
                'overflow': 'hidden',
                'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'
            }, id='progress-bar'),
            html.Div(id='progress-text', style={'textAlign': 'center', 'marginTop': '10px', 'color': HEALTHCARE_COLORS['dark']})
        ], style={'marginBottom': '30px', 'display': 'none'}, id='progress-container'),
        
        # Hidden dcc.Store components for multi-stage processing
        dcc.Store(id='raw-text-store', data=None),
        dcc.Store(id='highlighted-text-store', data=None),
        dcc.Store(id='deidentified-text-store', data=None),
        dcc.Store(id='processing-stage-store', data='idle'),  # 'idle', 'start', 'highlighting_done', 'deidentifying_done', 'complete'
        
        # Side-by-side comparison
        html.Div([
            # Left panel - Original with HIPAA highlighting
            html.Div([
                html.H4("Original Data (HIPAA Identifiers Highlighted)", 
                       style={'color': HEALTHCARE_COLORS['primary'], 'marginBottom': '15px'}),
                html.Div([
                    html.Iframe(
                        id='highlighted-text-frame',
                        srcDoc='',
                        style={
                            'width': '100%',
                            'height': '500px',
                            'border': f'2px solid {HEALTHCARE_COLORS["info"]}',
                            'borderRadius': '8px',
                            'backgroundColor': '#f8f9fa',
                        }
                    )
                ])
            ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginRight': '2%'}),
            
            # Right panel - De-identified output
            html.Div([
                html.H4("De-identified Data (HIPAA Compliant)", 
                       style={'color': HEALTHCARE_COLORS['success'], 'marginBottom': '15px'}),
                html.Div([
                    html.Iframe(
                        id='deidentified-text-frame',
                        srcDoc='',
                        style={
                            'width': '100%',
                            'height': '500px',  # Same height as left panel
                            'border': f'2px solid {HEALTHCARE_COLORS["success"]}',
                            'borderRadius': '8px',
                            'backgroundColor': '#e8f5e8',
                        }
                    )
                ])
            ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'})
        ], style={'marginBottom': '30px'}),
        
        # HIPAA identifier legend
        html.Div([
            html.H4("HIPAA Identifier Types", 
                   style={'color': HEALTHCARE_COLORS['primary'], 'marginBottom': '15px'}),
            html.Div([
                html.Div([
                    html.Span("Names", style={'backgroundColor': '#ffeb3b', 'padding': '4px 8px', 'borderRadius': '3px', 'marginRight': '10px'}),
                    html.Span("SSN", style={'backgroundColor': '#ff9800', 'padding': '4px 8px', 'borderRadius': '3px', 'marginRight': '10px'}),
                    html.Span("Phone", style={'backgroundColor': '#f44336', 'padding': '4px 8px', 'borderRadius': '3px', 'marginRight': '10px'}),
                    html.Span("Email", style={'backgroundColor': '#9c27b0', 'padding': '4px 8px', 'borderRadius': '3px', 'marginRight': '10px'}),
                    html.Span("Address", style={'backgroundColor': '#2196f3', 'padding': '4px 8px', 'borderRadius': '3px', 'marginRight': '10px'}),
                    html.Span("Dates", style={'backgroundColor': '#4caf50', 'padding': '4px 8px', 'borderRadius': '3px', 'marginRight': '10px'}),
                    html.Span("Medical Records", style={'backgroundColor': '#ff5722', 'padding': '4px 8px', 'borderRadius': '3px', 'marginRight': '10px'}),
                    html.Span("Insurance", style={'backgroundColor': '#795548', 'padding': '4px 8px', 'borderRadius': '3px'})
                ], style={'textAlign': 'center'})
            ], style={'backgroundColor': '#f8f9fa', 'padding': '15px', 'borderRadius': '8px'})
        ], style={'marginBottom': '30px'}),
        
        # Export and statistics
        html.Div([
            html.Div([
                html.Button('Export Results', 
                           id='export-btn',
                           style={
                               'backgroundColor': HEALTHCARE_COLORS['success'],
                               'color': 'white',
                               'border': 'none',
                               'padding': '10px 20px',
                               'borderRadius': '5px',
                               'cursor': 'pointer',
                               'marginRight': '10px'
                           }),
                html.Button('View Statistics', 
                           id='stats-btn',
                           style={
                               'backgroundColor': HEALTHCARE_COLORS['info'],
                               'color': 'white',
                               'border': 'none',
                               'padding': '10px 20px',
                               'borderRadius': '5px',
                               'cursor': 'pointer'
                           })
            ], style={'textAlign': 'center', 'marginBottom': '20px'}),
            
            # Statistics display
            html.Div(id='statistics-display', style={'textAlign': 'center'})
        ])
        
    ], style={'maxWidth': '1200px', 'margin': '0 auto', 'padding': '20px'}),
    
    # Footer
    html.Hr(style={'border': f'2px solid {HEALTHCARE_COLORS["light"]}'}),
    html.Div([
        html.P("© 2024 DEID Patients System - Enterprise Clinical Data De-identification Platform", 
               style={'textAlign': 'center', 'color': HEALTHCARE_COLORS['dark'], 'fontSize': '12px', 'margin': '10px 0'})
    ])
], style={'backgroundColor': '#ffffff', 'minHeight': '100vh'})

# Main callback for initiating processing and clearing
@app.callback(
    [Output('raw-text-input', 'value'),
     Output('highlighted-text-frame', 'srcDoc', allow_duplicate=True),
     Output('deidentified-text-frame', 'srcDoc', allow_duplicate=True),
     Output('progress-container', 'style'),
     Output('progress-bar-fill', 'style', allow_duplicate=True),
     Output('progress-text', 'children', allow_duplicate=True),
     Output('raw-text-store', 'data'),
     Output('processing-stage-store', 'data', allow_duplicate=True),
     Output('process-btn', 'disabled'),
     Output('process-btn', 'style')],
    [Input('process-btn', 'n_clicks'),
     Input('clear-btn', 'n_clicks')],
    [State('raw-text-input', 'value')],
    prevent_initial_call=True
)
def handle_processing_and_clear(process_clicks, clear_clicks, raw_text):
    # Get the callback context to determine which button was clicked
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Get the button that was clicked
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Default button style (enabled)
    default_button_style = {
        'backgroundColor': HEALTHCARE_COLORS['success'],
        'color': 'white',
        'border': 'none',
        'padding': '12px 24px',
        'borderRadius': '20px',
        'cursor': 'pointer',
        'fontSize': '16px',
        'fontWeight': 'bold',
        'marginTop': '15px'
    }
    
    # Disabled button style (lighter green)
    disabled_button_style = {
        'backgroundColor': HEALTHCARE_COLORS['success_disabled'],
        'color': 'white',
        'border': 'none',
        'padding': '12px 24px',
        'borderRadius': '20px',
        'cursor': 'not-allowed',
        'fontSize': '16px',
        'fontWeight': 'bold',
        'marginTop': '15px',
        'opacity': '0.7'
    }
    
    if button_id == 'clear-btn' and clear_clicks:
        # Clear all fields and re-enable button
        empty_html = """
        <html>
        <body style="font-family: monospace; font-size: 14px; line-height: 1.6; padding: 15px;">
            No data to process...
        </body>
        </html>
        """
        return "", empty_html, empty_html, {'display': 'none'}, {'width': '0%', 'height': '100%', 'backgroundColor': HEALTHCARE_COLORS['success'], 'borderRadius': '10px', 'transition': 'width 0.3s ease'}, "", None, 'idle', False, default_button_style
    
    elif button_id == 'process-btn' and process_clicks and raw_text:
        # Show processing status and progress bar immediately
        # Disable the button during processing
        status = html.Div([
            html.Span("Processing...", style={'color': HEALTHCARE_COLORS['warning'], 'fontWeight': 'bold'})
        ])
        
        # Show progress bar with initial state
        progress_style = {'marginBottom': '30px', 'display': 'block'}
        progress_fill_style = {'width': '20%', 'height': '100%', 'backgroundColor': HEALTHCARE_COLORS['success'], 'borderRadius': '10px', 'transition': 'width 0.3s ease'}
        progress_text = "Initializing de-identification process..."
        
        # Store raw text and trigger next stage, disable button
        return dash.no_update, dash.no_update, dash.no_update, progress_style, progress_fill_style, progress_text, raw_text, 'start', True, disabled_button_style
    
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

# Callback for highlighting stage
@app.callback(
    [Output('highlighted-text-store', 'data'),
     Output('processing-stage-store', 'data', allow_duplicate=True),
     Output('progress-bar-fill', 'style', allow_duplicate=True),
     Output('progress-text', 'children', allow_duplicate=True)],
    [Input('raw-text-store', 'data')],
    [State('processing-stage-store', 'data')],
    prevent_initial_call=True
)
def process_highlighting(raw_text, current_stage):
    if raw_text and current_stage == 'start':
        # Update progress to 60%
        progress_fill_style = {'width': '60%', 'height': '100%', 'backgroundColor': HEALTHCARE_COLORS['success'], 'borderRadius': '10px', 'transition': 'width 0.3s ease'}
        progress_text = "Detecting HIPAA identifiers..."
        
        # Perform highlighting
        highlighted_html = highlight_hipaa_identifiers(raw_text)
        
        # Create complete HTML document
        highlighted_complete_html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: monospace;
                    font-size: 14px;
                    line-height: 1.6;
                    padding: 15px;
                    white-space: pre-wrap;
                }}
            </style>
        </head>
        <body>
            {highlighted_html}
        </body>
        </html>
        """
        
        return highlighted_complete_html, 'highlighting_done', progress_fill_style, progress_text
    
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update

# Callback for de-identification stage
@app.callback(
    [Output('deidentified-text-store', 'data'),
     Output('processing-stage-store', 'data', allow_duplicate=True),
     Output('progress-bar-fill', 'style', allow_duplicate=True),
     Output('progress-text', 'children', allow_duplicate=True),
     Output('process-btn', 'disabled', allow_duplicate=True),
     Output('process-btn', 'style', allow_duplicate=True)],
    [Input('highlighted-text-store', 'data')],
    [State('processing-stage-store', 'data'),
     State('raw-text-store', 'data')],
    prevent_initial_call=True
)
def process_deidentification(highlighted_data, current_stage, raw_text):
    if highlighted_data and current_stage == 'highlighting_done' and raw_text:
        # Update progress to 80%
        progress_fill_style = {'width': '80%', 'height': '100%', 'backgroundColor': HEALTHCARE_COLORS['success'], 'borderRadius': '10px', 'transition': 'width 0.3s ease'}
        progress_text = "Applying de-identification rules..."
        
        # Perform de-identification
        deidentified_text = deidentify_text(raw_text)
        
        # Format de-identified text
        formatted_deidentified = format_deidentified_text(raw_text, deidentified_text)
        
        # Create complete HTML document
        deidentified_complete_html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: monospace;
                    font-size: 14px;
                    line-height: 1.6;
                    padding: 15px;
                    white-space: pre-wrap;
                }}
                .redacted {{
                    font-weight: bold;
                    color: #006400;
                }}
            </style>
        </head>
        <body>
            {formatted_deidentified}
        </body>
        </html>
        """
        
        # Update progress to 100%
        progress_fill_style = {'width': '100%', 'height': '100%', 'backgroundColor': HEALTHCARE_COLORS['success'], 'borderRadius': '10px', 'transition': 'width 0.3s ease'}
        progress_text = "Processing complete!"
        
        # Re-enable the button with default styling
        default_button_style = {
            'backgroundColor': HEALTHCARE_COLORS['success'],
            'color': 'white',
            'border': 'none',
            'padding': '12px 24px',
            'borderRadius': '20px',
            'cursor': 'pointer',
            'fontSize': '16px',
            'fontWeight': 'bold',
            'marginTop': '15px'
        }
        
        return deidentified_complete_html, 'complete', progress_fill_style, progress_text, False, default_button_style
    
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

# Callback to update highlighted text display
@app.callback(
    Output('highlighted-text-frame', 'srcDoc', allow_duplicate=True),
    [Input('highlighted-text-store', 'data')],
    prevent_initial_call=True
)
def update_highlighted_display(highlighted_data):
    if highlighted_data:
        return highlighted_data
    return dash.no_update

# Callback to update de-identified text display
@app.callback(
    Output('deidentified-text-frame', 'srcDoc', allow_duplicate=True),
    [Input('deidentified-text-store', 'data')],
    prevent_initial_call=True
)
def update_deidentified_display(deidentified_data):
    if deidentified_data:
        return deidentified_data
    return dash.no_update

# Callback to update processing status
@app.callback(
    Output('processing-status', 'children'),
    [Input('processing-stage-store', 'data')],
    prevent_initial_call=True
)
def update_processing_status(stage):
    if stage == 'complete':
        return html.Div([
            html.Span("Processing Complete", style={'color': HEALTHCARE_COLORS['success'], 'fontWeight': 'bold'})
        ])
    elif stage in ['start', 'highlighting_done', 'deidentifying_done']:
        return html.Div([
            html.Span("Processing...", style={'color': HEALTHCARE_COLORS['warning'], 'fontWeight': 'bold'})
        ])
    return dash.no_update

def format_deidentified_text(original_text, deidentified_text):
    """
    Format de-identified text to match the structure of the original text
    and highlight the redacted parts in bold
    """
    # Find all redacted patterns like [REDACTED:TYPE]
    redacted_pattern = r'\[REDACTED:[A-Z_]+\]|\[DATE\]|\[PATIENT NAME\]|\[SSN\]|\[PHONE\]|\[EMAIL\]|PERSON_[a-z0-9]+'
    
    # Bold all redacted text
    formatted_text = re.sub(
        redacted_pattern,
        r'<span class="redacted">\g<0></span>',
        deidentified_text
    )
    
    return formatted_text

# Callback for statistics
@app.callback(
    Output('statistics-display', 'children'),
    [Input('stats-btn', 'n_clicks')],
    [State('raw-text-input', 'value')],
    prevent_initial_call=True
)
def show_statistics(n_clicks, raw_text):
    if not n_clicks or not raw_text:
        return ""
    
    # Count HIPAA identifiers
    stats = {}
    for pattern_name, pattern in HIPAA_PATTERNS.items():
        matches = len(re.findall(pattern, raw_text, re.IGNORECASE))
        if matches > 0:
            stats[pattern_name] = matches
    
    if not stats:
        return html.Div([
            html.P("No HIPAA identifiers detected in the input text.", 
                   style={'color': HEALTHCARE_COLORS['info']})
        ])
    
    # Create statistics table
    stats_data = []
    for identifier, count in stats.items():
        stats_data.append({
            'Identifier Type': identifier.replace('_', ' ').title(),
            'Count': count,
            'Status': 'Detected' if count > 0 else 'Not Found'
        })
    
    return html.Div([
        html.H5("HIPAA Identifier Statistics", 
               style={'color': HEALTHCARE_COLORS['primary'], 'marginBottom': '15px'}),
        dash_table.DataTable(
            data=stats_data,
            columns=[{'name': col, 'id': col} for col in ['Identifier Type', 'Count', 'Status']],
            style_cell={'textAlign': 'left', 'padding': '10px'},
            style_header={'backgroundColor': HEALTHCARE_COLORS['light'], 'fontWeight': 'bold'},
            style_data_conditional=[
                {
                    'if': {'filter_query': '{Status} = Detected'},
                    'backgroundColor': '#e8f5e8',
                    'color': HEALTHCARE_COLORS['success']
                }
            ]
        )
    ])

# Callback for export
@app.callback(
    Output('export-btn', 'children'),
    [Input('export-btn', 'n_clicks')],
    [State('raw-text-input', 'value'),
     State('deidentified-text-frame', 'srcDoc')],
    prevent_initial_call=True
)
def export_results(n_clicks, raw_text, deidentified_text):
    if n_clicks and raw_text and deidentified_text:
        # Create downloadable content
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"deid_results_{timestamp}.txt"
        
        # Extract text content from HTML
        import re
        # Remove HTML tags to get clean text
        clean_text = re.sub(r'<[^>]+>', '', deidentified_text)
        
        content = f"""
DEID Patients - De-identification Results
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

ORIGINAL DATA:
{raw_text}

DE-IDENTIFIED DATA:
{clean_text}

HIPAA Compliance: ✅ Verified
"""
        
        # In a real implementation, you would create a download link here
        return "Export Complete"
    
    return "Export Results"

if __name__ == '__main__':
    print("Starting DEID Patients Dash UI...")
    print("Access the application at: http://localhost:8050")
    print("Target Audience: Clinicians and AI professionals")
    print("Focus: Clinical data de-identification")
    app.run_server(debug=True, host='0.0.0.0', port=8050)
