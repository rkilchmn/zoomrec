import os
import argparse
import logging
from typing import Optional

from shared.ai_service import LLMChat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def read_file(filepath: str) -> str:
    """Read the content of a text file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except Exception as e:
        logger.error(f"Error reading file {filepath}: {str(e)}")
        raise

def generate_summary(text: str, filename: str, llm: LLMChat) -> Optional[str]:
    """Generate a summary of the given text using the LLM."""

    # remove /mnt/zoomrec/ from filename
    filename = filename.replace("/mnt/c/", "/C:/")
    video_file = os.path.splitext(filename)[0] + ".mkv"
    prompt = f"""
You are a helpful assistant. Analyze the following transcript:

1. Identify all major topic changes.
2. Summarize each topic with:
   - Title and timestamp range 
   - Summary
   - highlight actionable trades with tickers limit and buy conditions (if/then)
   - Link to video file (example): [▶️ Open in VLC](vlc://file://{video_file}?start-time=<replace with start timestamp in seconds>)
   - Include inline chart (example TSLA): ![TSLA Chart](https://finviz.com/chart.ashx?t=TSLA&ty=c&ta=1&p=d&s=l)

Transcript (as VTT file with timestamp format Minutes:Seconds:Milliseconds)
{text}
    """
    
    logger.info("Generating summary...")
    return llm.ask(prompt)

def main():
    parser = argparse.ArgumentParser(description='Generate AI-powered summaries of text files.')
    parser.add_argument('filename', type=str, help='Path to the text file to summarize')
    parser.add_argument('--model', type=str, default="meta-llama/llama-4-maverick",
                       help='Model to use for summarization (default: meta-llama/llama-4-maverick)')
    parser.add_argument('--output', type=str, help='Output file to save the summary (optional, defaults to input filename with .md extension)')
    parser.add_argument('--no-output', action='store_true', help='Disable saving to file')
    parser.add_argument('--api-url', type=str, 
                       default="https://openrouter.ai/api/v1",
                       help='API base URL (default: OpenRouter)')
    parser.add_argument('--api-key-env', type=str, default="OPENROUTER_API_KEY",
                       help='Environment variable containing the API key (default: OPENROUTER_API_KEY)')
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.isfile(args.filename):
        logger.error(f"File not found: {args.filename}")
        return
    
    try:
        # Initialize LLM client
        llm = LLMChat(
            model=args.model,
            api_url=args.api_url,
            api_key_env=args.api_key_env
        )
        
        # Read and summarize the file
        text = read_file(args.filename)
        summary = generate_summary(text, args.filename, llm)
        
        if not summary:
            logger.error("Failed to generate summary")
            return
        
        # Output the summary
        print("\n=== SUMMARY ===\n")
        print(summary)
        
        # Save to file if not disabled
        if not args.no_output:
            output_file = args.output
            if not output_file:
                # If no output file specified, use input filename with .md extension
                base_name = os.path.splitext(args.filename)[0]
                output_file = f"{base_name}.md"
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(summary)
                logger.info(f"Summary saved to {output_file}")
            except Exception as e:
                logger.error(f"Error saving summary to file: {str(e)}")
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
