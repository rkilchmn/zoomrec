#!/usr/bin/env python3
import os
import argparse
import logging
from typing import Optional
import re
import sys

from shared.ai_service import LLMChat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def read_file(filepath: str) -> str:
    """Read the content of a input file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except Exception as e:
        logger.error(f"Error reading file {filepath}: {str(e)}")
        raise

def generate_summary(content: str, recording_link: str, prompt: str, llm: LLMChat) -> Optional[str]:
    """Generate a summary of the given content using the LLM.
    
    Args:
        content: The content to summarize
        filename: The name of the file being processed
        prompt: The prompt template to use (can include {content}, {link})
        llm: The LLM client to use for generation
        link: Optional link to include in the prompt
    """
    format_args = {
        'content': content,
        'recording-link': recording_link
    }
    prompt = prompt.format(**format_args)

    return llm.ask(prompt)

def validate_arguments(args: argparse.Namespace) -> None:
    """Validate that all required arguments are provided and valid."""
    errors = []

    if not args.recording_filename:
        errors.append("recording_filename is required")
    
    if not args.prompt:
        errors.append("--prompt is required")

    if not args.content_filename_regex:
        errors.append("--content-filename-regex is required")   
    
    # Check API key environment variable
    if not os.getenv(args.api_key_env):
        errors.append(f"API key environment variable '{args.api_key_env}' is not set")
    
    # Validate output extension starts with a dot
    if args.output_extension and not args.output_extension.startswith('.'):
        args.output_extension = f".{args.output_extension}"
    
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        print("\nUsage:")
        print("  summarize_transcript.py recording_filename --prompt PROMPT --content-filename-regex REGEX [options]")
        print("\nRequired arguments:")
        print("  recording_filename     Path to the recording file to summarize. ")
        print("  --prompt PROMPT        Prompt to use for summarization. Use {input} for the input file content and {filename} for the input file name")
        print("  --content-filename-regex REGEX Regex to transform recording filename to the input file containing the content to summarize that needs to be used in the prompt as {content}")
        print("\nOptional arguments:")
        print("  --api-url URL          API base URL (default: https://openrouter.ai/api/v1)")
        print("  --api-key-env VAR      Environment variable containing the API key (default: OPENROUTER_API_KEY)")
        print("  --model MODEL          Model to use for summarization (default: meta-llama/llama-4-maverick)")
        print("  --output-filename FILE Output file (default: input filename with specified extension)")
        print("  --output-extension EXT File extension for output (default: .md)")
        print("  --no-output           Write to stdout instead of file")
        print("  --max-retries N       Maximum retry attempts (default: 3)")
        print("  --link-filename-regex REGEX Regex to transform recording filename to the link to the recording file that can be used in the prompt as {link} if it needs transformation for some reason to work.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Generate AI-powered summaries of input files.',
                                    add_help=False)  # We'll handle help manually
    # Required arguments
    required = parser.add_argument_group('required arguments')
    required.add_argument('recording_filename', type=str, help='Path to the recording file to summarize')
    required.add_argument('--content-filename-regex', type=str, help='Regex to transform recording filename to the filename that contains the content to summarize, referred to as {content} in the prompt.')
    required.add_argument('--prompt', type=str, required=True, help='Prompt to use for summarization. Available substitutions: {input}, {filename}')
    
    # Optional arguments
    optional = parser.add_argument_group('optional arguments')
    optional.add_argument('-h', '--help', action='store_true', help='Show this help message and exit')
    optional.add_argument('--recording-link-regex', type=str, help='Optional Regex to be used to transform recording filename to a link to the recording file that can be used in the prompt as {link}. If not used {link} will be the recording filename.')
    optional.add_argument('--model', type=str, default="meta-llama/llama-4-maverick",
                         help='Model to use for summarization (default: %(default)s)')
    optional.add_argument('--output-filename', type=str, 
                         help='Output file (default: input filename with specified extension)')
    optional.add_argument('--output-extension', type=str, default='.md',
                         help='File extension for output (default: %(default)s)')
    optional.add_argument('--no-output', action='store_true', 
                         help='Write to stdout instead of file (default: %(default)s)')
    optional.add_argument('--api-url', type=str, default="https://openrouter.ai/api/v1",
                         help='API base URL (default: %(default)s)')
    optional.add_argument('--api-key-env', type=str, default="OPENROUTER_API_KEY",
                         help='Environment variable containing the API key (default: %(default)s)')
    optional.add_argument('--max-retries', type=int, default=3,
                         help='Maximum retry attempts (default: %(default)d)')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle --help manually to show custom help
    if args.help:
        parser.print_help()
        sys.exit(0)
    
    # Validate arguments  
    validate_arguments(args)
    
    # Validate input file
    if not os.path.isfile(args.recording_filename):
        logger.error(f"Recording file not found: {args.recording_filename}")
        exit(2)
    
    try:
        # Initialize LLM client
        llm = LLMChat(
            model=args.model,
            api_url=args.api_url,
            api_key_env=args.api_key_env,
            max_retries=args.max_retries
        )
        
        # Apply filename transformations
        content_filename = None
        recording_link = args.recording_filename
        
        # Process input filename regex if provided
        if args.content_filename_regex:
            try:
                pattern, replacement = args.content_filename_regex.split("|||", 1)
                content_filename = re.sub(pattern, replacement, args.recording_filename)
            except ValueError:
                logger.error(f"Invalid content-filename-regex format. Expected 'pattern|||replacement', got '{args.content_filename_regex}'")
                exit(3)
        
        # Process link filename regex if provided
        if args.recording_link_regex:
            try:
                pattern, replacement = args.recording_link_regex.split("|||", 1)
                recording_link = re.sub(pattern, replacement, args.recording_filename)
            except ValueError:
                logger.error(f"Invalid recording-link-regex format. Expected 'pattern|||replacement', got '{args.recording_link_regex}'")
                exit(5)
        
        # Read content file
        if content_filename and os.path.isfile(content_filename):
            content = read_file(content_filename)
        else:
            logger.error(f"Content file not found: {content_filename}")
            exit(6)
        
        # Generate summary with all available context
        summary = generate_summary(content, recording_link, args.prompt, llm)
        
        if not summary:
            logger.error("Failed to generate summary")
            exit(7)
        
        # Save to file if not disabled
        if not args.no_output:
            output_file = args.output_filename  
            if not output_file:
                # If no output file specified, use recording filename with specified extension
                base_name = os.path.splitext(args.recording_filename)[0]
                # Ensure extension starts with a dot
                extension = args.output_extension if args.output_extension.startswith('.') else f'.{args.output_extension}'
                output_file = f"{base_name}{extension}"
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(summary)
                logger.info(f"Summary saved to {output_file}")
            except Exception as e:
                logger.error(f"Error saving summary to file: {str(e)}")
                exit(8)
        else:
            print(summary)

        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        exit(9)

if __name__ == "__main__":
    main()
