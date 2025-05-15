import pandas as pd
import json
import io
import re
import base64
import random
import requests
from pathlib import Path
from PIL import Image
from typing import List, Dict, Union, Optional, Any
import argparse
import os

class JsonVisualizer:
    """A framework for visualizing JSON data as interactive HTML tables with dynamic column toggling."""
    
    @staticmethod
    def read_json(input_file: str) -> pd.DataFrame:
        """Read JSON or JSONL file into a pandas DataFrame."""
        return pd.read_json(input_file, orient='records', lines=input_file.endswith('.jsonl'))
    
    @staticmethod
    def image_to_base64(image_path_or_sth, to_base64=True):
        """Convert image to base64 encoding for embedding in HTML.
        
        Args:
            image_path_or_sth: Can be a path string, Path object, BytesIO object, or PIL Image
            to_base64: Whether to return as base64 (True) or as bytes (False)
        
        Returns:
            Base64 encoded string or byte array
        """
        byte_arr = None

        # Case 1: Path(or url) to the image
        if isinstance(image_path_or_sth, str):
            if image_path_or_sth.startswith('http://') or image_path_or_sth.startswith('https://'):
                # Case 2: URL pointing to the image
                response = requests.get(image_path_or_sth)
                response.raise_for_status()  # Ensure we notice bad responses
                byte_arr = response.content
            else:
                # Local file path
                try:
                    with open(image_path_or_sth, "rb") as image_file:
                        byte_arr = image_file.read()
                except FileNotFoundError:
                    # Return a placeholder image or error message
                    byte_arr = b''
        elif isinstance(image_path_or_sth, Path):
            # Local Path object
            try:
                with open(image_path_or_sth, "rb") as image_file:
                    byte_arr = image_file.read()
            except FileNotFoundError:
                byte_arr = b''
        elif isinstance(image_path_or_sth, io.BytesIO):
            # Case 3: Image loaded in memory as BytesIO
            byte_arr = image_path_or_sth.getvalue()
        elif hasattr(image_path_or_sth, 'save'):
            # Case 4: Assume it is a PIL Image object
            byte_arr = io.BytesIO()
            image_path_or_sth.save(byte_arr, format='PNG')
            byte_arr = byte_arr.getvalue()
        else:
            # Cannot process this image
            byte_arr = b''
            
        if to_base64 and byte_arr:
            encoded_string = base64.b64encode(byte_arr).decode('utf-8')
            return encoded_string
        else:
            return byte_arr

    @staticmethod
    def image_to_html(image_path_or_sth, width=320):
        """Convert image to HTML img tag with base64 data URI.
        
        Args:
            image_path_or_sth: Image path, URL, BytesIO, or PIL Image
            width: Width of displayed image in HTML
            
        Returns:
            HTML img tag with embedded image data
        """
        if not isinstance(image_path_or_sth, (str, Path, io.BytesIO, Image.Image)) or not image_path_or_sth:
            return '<div class="missing-image">No image available</div>'
        
        encoded_image = JsonVisualizer.image_to_base64(image_path_or_sth)
        if not encoded_image:
            return '<div class="missing-image">Image not found</div>'
            
        template = f'<img src="data:image/png;base64,{encoded_image}" width="{width}" alt="Embedded Image">'
        return template
    
    @staticmethod
    def process_textual_content(text, is_markdown=False):
        """Process textual content for HTML display.
        
        Args:
            text: The text to process
            is_markdown: Whether to treat content as markdown
            
        Returns:
            Processed HTML-safe text
        """
        if not isinstance(text, str):
            text = str(text)
            
        # Handle markdown code blocks if detected
        if is_markdown or (text and '```' in text.split('\n', 1)[0]):
            # Simple markdown code block extraction (could be expanded)
            pattern = r'```(markdown)?\s*(.*?)\s*```'
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                extracted = [match[1] for match in matches if match[1]]
                if extracted:
                    text = extracted[0]
        
        # Convert newlines to <br> tags
        text = text.strip().replace('\n', '<br>').replace('\\n', '<br>')
        
        # Replace special tags with HTML-safe equivalents
        special_tags = ['<image>', '<img>', '<think>', '</think>', '<answer>', '</answer>', 
                        '<observe>', '</observe>', '<highlight>', '</highlight>']
        for tag in special_tags:
            text = text.replace(tag, tag.replace('<', '&lt;').replace('>', '&gt;'))
        
        # Handle math notation
        text = text.replace('$$', '$')
        text = re.sub(r'\$(.*?)\$', r'\( \1 \)', text)
        
        return text
    
    @staticmethod
    def process_dataframe(df: pd.DataFrame, textual_cols=None, 
                          merge_cols=None, drop_cols=None) -> pd.DataFrame:
        """Process a dataframe to prepare it for HTML visualization.
        
        Args:
            df: Input pandas DataFrame
            textual_cols: List of columns containing text to be specially processed
            merge_cols: List of columns to merge into a single column
            drop_cols: List of columns to exclude from the output
            
        Returns:
            Processed pandas DataFrame
        """
        # Make a copy to avoid modifying the original
        df = df.copy()
        
        # Default lists if not provided
        if textual_cols is None:
            textual_cols = ['q & a', 'result', 'question', 'answer']
        
        if drop_cols is None:
            drop_cols = []
        
        # Convert dictionary/object columns to JSON strings with better formatting
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                df[col] = df[col].apply(lambda x: json.dumps(x, indent=2, ensure_ascii=False).replace('\n', '<br>').replace(' ', '&nbsp;') if isinstance(x, (dict, list)) else x)
        
        # Process image columns
        for col in df.columns:
            if 'image' in col.lower() or 'graph' in col.lower():
                df[col] = df[col].apply(lambda x: JsonVisualizer.image_to_html(x))
        
        # Process text columns
        for col in df.columns:
            # Check if it's a textual column by name pattern or explicit list
            is_textual = (col in textual_cols or col.lower() in textual_cols or
                         any(pattern in col.lower() for pattern in 
                             ['result', 'prompt', 'question', 'answer', 'q & a', 
                              'predict', 'judge', 'caption', 'cot', 'claude', 
                              'res', 'parse', 'truth', 'desc', 'info']))
            
            if is_textual:
                df[col] = df[col].apply(lambda x: JsonVisualizer.process_textual_content(x))
        
        # Merge columns if specified
        if merge_cols and len(merge_cols) > 1:
            # Check that all columns exist in the DataFrame
            valid_merge_cols = [col for col in merge_cols if col in df.columns]
            if len(valid_merge_cols) > 1:
                new_col_name = ' & '.join(valid_merge_cols)
                df[new_col_name] = df.apply(lambda x: '<br>'.join([str(x[col]) for col in valid_merge_cols]), axis=1)
                
                # Drop the source columns
                df = df.drop(columns=valid_merge_cols)
                
                # Move the merged column to the front
                cols = df.columns.tolist()
                cols.remove(new_col_name)
                df = df[[new_col_name] + cols]
        
        # Drop specified columns
        if drop_cols:
            df = df.drop(columns=[col for col in drop_cols if col in df.columns])
        
        return df
    
    @staticmethod
    def generate_html(df: pd.DataFrame, title: str = "JSON Visualizer", original_data: pd.DataFrame = None) -> str:
        """Generate HTML string with the interactive table.
        
        Args:
            df: Processed pandas DataFrame
            title: Title for the HTML page
            original_data: Original DataFrame for resampling
            
        Returns:
            HTML content as a string
        """
        # Convert DataFrame to HTML table without index
        df_html = df.to_html(render_links=True, escape=False, classes='data-table', index=False)
        
        
        # Store original data as JSON in a hidden element
        # original_data_json = ''
        # if original_data is not None:
        #     # 将列名和数据一起保存，以便正确重建
        #     columns = original_data.columns.tolist()
        #     data = original_data.values.tolist()
        #     original_data_dict = {
        #         'columns': columns,
        #         'data': data
        #     }
        #     original_data_json = json.dumps(original_data_dict)
        # 用pandas转json
        original_data_json = original_data.to_json(orient='split')

        
        # External CSS and JS resources
        bootstrap_css = "https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css"
        datatables_css = "https://cdn.datatables.net/1.13.4/css/dataTables.bootstrap5.min.css"
        jquery_js = "https://code.jquery.com/jquery-3.6.0.min.js"
        datatables_js = "https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"
        datatables_bootstrap_js = "https://cdn.datatables.net/1.13.4/js/dataTables.bootstrap5.min.js"
        mathjax_js = "https://cdn.bootcdn.net/ajax/libs/mathjax/3.2.2/es5/tex-chtml.js"
        
        # Custom CSS for the table and controls
        custom_css = """
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f8f9fa;
        }
        .container {
            max-width: 95%;
            margin: 0 auto;
        }
        .controls {
            background-color: #ffffff;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .column-toggle {
            margin-bottom: 10px;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
        }
        .data-table th {
            background-color: #f8f9fa;
            position: sticky;
            top: 0;
            z-index: 10;
            box-shadow: 0 1px 1px rgba(0,0,0,0.1);
        }
        .data-table td, .data-table th {
            padding: 8px;
            border: 1px solid #dee2e6;
            word-wrap: break-word;
        }
        .data-table td {
            vertical-align: top;
            max-width: 500px;
        }
        img {
            max-width: 100%;
            height: auto;
        }
        .hide {
            display: none;
        }
        .btn-toggle {
            margin: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 200px;
        }
        .column-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-top: 10px;
        }
        #search {
            width: 100%;
            padding: 8px;
            margin-bottom: 10px;
            border: 1px solid #ced4da;
            border-radius: 4px;
        }
        .missing-image {
            color: #6c757d;
            font-style: italic;
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            text-align: center;
        }
        .heading {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        #resampleControls {
            margin-bottom: 15px;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 5px;
        }
        #resampleSize {
            width: 100px;
            margin-right: 10px;
        }
        """
        
        # JavaScript for dynamic column toggling and additional features
        custom_js = """
        $(document).ready(function() {
            // 解析原始数据
            var originalDataObj = """ + original_data_json + """;
            
            // Initialize DataTable with custom page length options
            var table = $('.data-table').DataTable({
                paging: true,
                searching: true,
                ordering: true,
                info: true,
                lengthMenu: [
                    [10, 25, 50, 100, 200, 500, -1],
                    [10, 25, 50, 100, 200, 500, "All"]
                ],
                dom: '<"top"lf>rt<"bottom"ip><"clear">',
                columnDefs: [
                    { orderable: false, targets: '_all' }
                ]
            });
            
            // 添加自定义页面长度输入
            var lengthDiv = $('.dataTables_length');
            lengthDiv.append(
                '<div style="display: inline-block; margin-left: 15px;">' +
                '<input type="number" id="customPageLength" placeholder="Custom" style="width: 80px">' +
                '<button class="btn btn-sm btn-secondary" onclick="setCustomPageLength()">Set</button>' +
                '</div>'
            );
            
            window.setCustomPageLength = function() {
                var length = parseInt($('#customPageLength').val());
                if (length > 0) {
                    table.page.len(length).draw();
                }
            };
            
            // 重新采样功能（仅在有原始数据时添加）
            if (originalDataObj && originalDataObj.columns && originalDataObj.data) {
                var controlsDiv = $('.controls');
                var totalRows = originalDataObj.data.length;
                
                var resampleControls = $('<div id="resampleControls">' +
                    '<label>Resample size: </label>' +
                    '<input type="number" id="resampleSize" min="1" max="' + totalRows + '" placeholder="Size">' +
                    '<button class="btn btn-primary btn-sm" onclick="resampleData()">Resample</button>' +
                    '<span style="margin-left: 10px;">Total: ' + totalRows + '</span>' +
                    '</div>'
                );
                controlsDiv.prepend(resampleControls);
                
                window.resampleData = function() {
                    var size = parseInt($('#resampleSize').val());
                    if (size > 0 && size <= totalRows) {
                        // Fisher-Yates shuffle on indices
                        var indices = Array.from(Array(totalRows).keys());
                        for (let i = indices.length - 1; i > 0; i--) {
                            const j = Math.floor(Math.random() * (i + 1));
                            [indices[i], indices[j]] = [indices[j], indices[i]];
                        }
                        
                        // Select the first 'size' elements as indices
                        var sampledIndices = indices.slice(0, size);
                        
                        // Get the sampled data using the indices
                        var sampledData = sampledIndices.map(i => originalDataObj.data[i]);
                        
                        // Clear and reload table
                        table.clear();
                        table.rows.add(sampledData);
                        table.draw();
                        
                        // Update row count badge
                        $('.badge.bg-primary').text(size + ' rows');
                    }
                };
            }
            
            // Create column toggle buttons dynamically
            var columnButtons = $('.column-buttons');
            
            // Add "Toggle All" button
            $('<button class="btn btn-primary btn-toggle btn-sm" data-toggle="all">Toggle All</button>')
                .on('click', function() {
                    var allVisible = true;
                    table.columns().every(function() {
                        if (!this.visible()) {
                            allVisible = false;
                            return false;
                        }
                    });
                    
                    table.columns().visible(allVisible ? false : true);
                    $('.btn-toggle[data-column]').toggleClass('btn-primary btn-secondary', !allVisible);
                })
                .appendTo(columnButtons);
                
            // Add column-specific toggle buttons
            table.columns().every(function(index) {
                var column = this;
                var colName = $(column.header()).text();
                $('<button class="btn btn-primary btn-toggle btn-sm" data-column="' + index + '" title="' + colName + '">' + colName + '</button>')
                    .on('click', function() {
                        column.visible(!column.visible());
                        $(this).toggleClass('btn-primary btn-secondary');
                    })
                    .appendTo(columnButtons);
            });
            
            // Search functionality
            $('#search').on('keyup', function() {
                table.search($(this).val()).draw();
            });
        });
        """
        
        # Assemble the HTML document
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <link rel="stylesheet" href="{bootstrap_css}">
            <link rel="stylesheet" href="{datatables_css}">
            <style>{custom_css}</style>
        </head>
        <body>
            <div class="container">
                <div class="heading">
                    <h1>{title}</h1>
                    <div>
                        <span class="badge bg-primary">{len(df)} rows</span>
                        <span class="badge bg-secondary">{len(df.columns)} columns</span>
                    </div>
                </div>
                
                <div class="controls">
                    <input type="text" id="search" placeholder="Search in table...">
                    <div class="column-toggle">
                        <h5>Toggle Columns:</h5>
                        <div class="column-buttons">
                            <!-- Buttons will be inserted here by JavaScript -->
                        </div>
                    </div>
                </div>
                
                <div class="table-responsive">
                    {df_html}
                </div>
            </div>
            
            <script src="{jquery_js}"></script>
            <script src="{datatables_js}"></script>
            <script src="{datatables_bootstrap_js}"></script>
            <script src="{mathjax_js}" async></script>
            <script>{custom_js}</script>
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    def visualize(input_file: str, output_file: str = None, sample_size: int = None,
                 textual_cols: List[str] = None, merge_cols: List[str] = None, 
                 drop_cols: List[str] = None, title: str = None):
        """Main method to visualize JSON data as an interactive HTML table.
        
        Args:
            input_file: Path to the JSON or JSONL file
            output_file: Path to save the HTML output. If None, will use input_file with .html extension
            sample_size: Number of rows to sample (random). If None, use all data
            textual_cols: List of column names to treat as text content
            merge_cols: List of column names to merge into a single column
            drop_cols: List of column names to exclude
            title: Title for the HTML page
        
        Returns:
            Path to the generated HTML file
        """
        # Set default output file if not provided
        if output_file is None:
            output_file = os.path.splitext(input_file)[0] + '.html'
            
        # Set default title if not provided
        if title is None:
            title = os.path.basename(os.path.splitext(input_file)[0])
            
        # Read the JSON/JSONL data into a DataFrame
        original_df = JsonVisualizer.read_json(input_file)
        
        # Sample if requested
        df = original_df.copy()
        if sample_size and sample_size < len(df):
            df = df.sample(sample_size, random_state=42)
            
        # Process the DataFrame
        df = JsonVisualizer.process_dataframe(
            df, 
            textual_cols=textual_cols,
            merge_cols=merge_cols,
            drop_cols=drop_cols
        )
        
        # Process original data for resampling
        original_df = JsonVisualizer.process_dataframe(
            original_df,
            textual_cols=textual_cols,
            merge_cols=merge_cols,
            drop_cols=drop_cols
        )
        
        # Generate the HTML content
        html_content = JsonVisualizer.generate_html(df, title=title, original_data=original_df)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        
        # Write the HTML file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"Visualization saved to: {output_file}")
        return output_file

# CLI interface for the library
def main():
    parser = argparse.ArgumentParser(description='Visualize JSON/JSONL data as interactive HTML tables')
    parser.add_argument('input_file', help='Path to input JSON or JSONL file')
    parser.add_argument('--output', '-o', help='Path to output HTML file (default: same as input with .html extension)')
    parser.add_argument('--sample', '-s', type=int, help='Sample size (number of rows to randomly select)')
    parser.add_argument('--title', '-t', help='Title for the HTML page')
    parser.add_argument('--textual-cols', nargs='+', help='List of columns to treat as text content')
    parser.add_argument('--merge-cols', nargs='+', help='List of columns to merge into single column')
    parser.add_argument('--drop-cols', nargs='+', help='List of columns to exclude from output')
    
    args = parser.parse_args()
    
    JsonVisualizer.visualize(
        input_file=args.input_file,
        output_file=args.output,
        sample_size=args.sample,
        textual_cols=args.textual_cols,
        merge_cols=args.merge_cols,
        drop_cols=args.drop_cols,
        title=args.title
    )

if __name__ == "__main__":
    main()