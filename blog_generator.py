import os
import re
import random
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from google_images_search import GoogleImagesSearch
from pinterest.client import PinterestSDKClient
from pinterest.organic.pins import Pin
import base64
import requests
from utils import anycode_prompt, moroccoheritage_prompt, user_prompt
from ignore import website, topics 
from openai import OpenAI

class BlogGenerator:
    def __init__(self, website="1"):
        """
        Initialize the BlogGenerator with website configuration.
        Args:
            website (str): "1" for moroccoheritage, "2" for gobitcode
        """
        self.website = website
        self.setup_paths()
        self.load_environment()

    def setup_paths(self):
        """Set up the file paths based on website configuration"""
        if self.website == 1:
            self.system_prompt = moroccoheritage_prompt
            self.blog_path = "/home/adil/repo/morocco-heritage/data/blog/"
            self.image_path = "/home/adil/repo/morocco-heritage/public/static/images"
            self.url = "https://moroccoheritage.com"
            self.pinterest_board_id = None
        elif self.website == 2:
            self.system_prompt = anycode_prompt
            self.blog_path = "/home/adil/repo/gobitcode/data/blog/"
            self.image_path = "/home/adil/repo/gobitcode/public/static/images"
            self.url = "https://anycode.it"
            self.pinterest_board_id = "1136244249676952980"
        else:
            raise ValueError("Invalid website configuration")

    def load_environment(self):
        """Load environment variables and API keys"""
        load_dotenv()
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        self.google_cx = os.getenv('GOOGLE_CX')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        

    @staticmethod
    def generate_slug(title):
        """Generate a URL-friendly slug from a title"""
        slug = title.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        return slug.strip('-')

    def download_images(self, keyword, path, limit=1):
        """
        Download images from Google Images and rename them with slugified names
        Args:
            keyword (str): Search keyword for images
            path (str): Directory to save images
            limit (int): Number of images to download
        Returns:
            str or None: New filename of the downloaded image, None if no image found
        """
        try:
            gis = GoogleImagesSearch(self.google_api_key, self.google_cx)
            
            search_params = {
                'q': keyword,
                'num': limit,
                'safe': 'off',
            }

            gis.search(search_params=search_params)
            results = gis.results()
            
            if not results:
                print(f"Warning: No images found for keyword: {keyword}")
                return None
                
            image = results[0]
            image.download(path)
            
            # Rename the downloaded image
            old_image_name = os.path.basename(image.path)
            filename, extension = os.path.splitext(old_image_name)
            new_image_name = f"{self.generate_slug(filename)}{extension}"
            os.rename(image.path, os.path.join(path, new_image_name))
            
            return new_image_name
        except Exception as e:
            print(f"Error downloading image for keyword '{keyword}': {str(e)}")
            return None

    def generate_blog(self, seo_keywords, use_openai=True):
        """
        Generate a blog post using either Groq or OpenAI API
        Args:
            seo_keywords (str): Main topic/keywords for the blog
            use_openai (bool): If True use OpenAI API, else use Groq API
        Returns:
            str: Generated blog content
        """
        if not use_openai:
            client = Groq(api_key=self.groq_api_key)
            completion = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt(seo_keywords)
                    }
                ],
                temperature=0.7,
                max_tokens=1024*8,
                max_completion_tokens=1024*8,
                top_p=1,
                stream=False,
                stop=None,
            )
            return completion.choices[0].message.content
        else:
            
            client = OpenAI(api_key=self.openai_api_key)
            completion  = client.responses.create(
            model="gpt-4.1",
            input=[
                {
                "role": "system",
                "content": [
                    {
                    "type": "input_text",
                    "text": self.system_prompt
                    }
                ]
                },
                {
                "role": "user",
                "content": [
                    {
                    "type": "input_text",
                    "text": user_prompt(seo_keywords)
                    }
                ]
                }
            ],
            text={
                "format": {
                "type": "text"
                }
            },
            reasoning={},
            tools=[],
            temperature=1,
            max_output_tokens=2**63 -1,
            top_p=1,
            stream=False,
            )
            return completion.output_text

    def process_images(self, mdx_blog, image_folder):
        """
        Process and download images for the blog
        Args:
            mdx_blog (str): Blog content with image tags
            image_folder (str): Folder to save images
        Returns:
            str: Updated blog content with new image paths or removed image tags
        """
        img_tag_regex = r'<img[^>]*alt=\"([^\"]*)\"[^>]*>'
        matches = re.findall(img_tag_regex, mdx_blog)
        paths = []
        
        for match in matches:
            image_name = self.download_images(
                f"{self.seo_keywords} {match}",
                os.path.join(self.image_path, image_folder)
            )
            
            if image_name:
                # Successfully downloaded image, update the src attribute
                new_src = f'/static/images/{image_folder}/{image_name}'
                paths.append(os.path.join(self.image_path, image_folder, image_name))
                mdx_blog = re.sub(
                    rf'(<img[^>]*src=\")[^\"]*(\"[^>]*alt=\"{re.escape(match)}\"[^>]*>)',
                    rf'\1{new_src}\2',
                    mdx_blog
                )
            else:
                # Failed to download image, remove the entire img tag
                print(f"Removing image tag for alt text: {match}")
                mdx_blog = re.sub(
                    rf'<img[^>]*alt=\"{re.escape(match)}\"[^>]*>',
                    '',
                    mdx_blog
                )
        
        return mdx_blog, paths

    def correct_title(self, mdx_blog):
        """Remove ':', "'", and '"' when they appear after 'title:' or 'summary:'"""
        lines = mdx_blog.splitlines()
        new_lines = []
        for line in lines:
            if line.startswith("title:"):
                prefix, rest = line[:6], line[6:]
                rest = rest.replace(":", " ").replace("'", " ").replace('"', " ")
                line = prefix + rest
            elif line.startswith("summary:"):
                prefix, rest = line[:8], line[8:]
                rest = rest.replace(":", " ").replace("'", " ").replace('"', " ")
                line = prefix + rest
            new_lines.append(line)
        return "\n".join(new_lines)

    def correct_date(self, mdx_blog):
        """Update the date to today's date in the correct format"""
        today = datetime.now().strftime('%Y-%m-%d')
        date_regex = r'^(date:)\s*["\']?(\d{4}-\d{2}-\d{2})["\']?$'
        return re.sub(date_regex, rf"\1 '{today}'", mdx_blog, count=1, flags=re.MULTILINE)

    def save_blog(self, mdx_blog, slug):
        """Save the blog content to an MDX file"""
        filename = f"{slug}.mdx"
        blog_save_path = os.path.join(self.blog_path, filename)
        
        with open(blog_save_path, 'w') as file:
            file.write(mdx_blog)
        
        return filename

    def create_pinterest_pin(self, image_path, title, description,link, board_id):
        """
        Create a pin on Pinterest board using a local image file
        
        Args:
            image_path (str): Local path to the image file
            title (str): Title of the pin
            description (str): Description of the pin
            board_id (str): ID of the Pinterest board to pin to
            
        Returns:
            tuple: Pin ID and Pin Title if successful, (None, None) if failed
        """
        try:
            # Get client credentials
            client_id = os.getenv('PINTEREST_CLIENT_ID')
            client_secret = os.getenv('PINTEREST_CLIENT_SECRET')

            # Encode credentials for Basic Authentication
            credentials = f"{client_id}:{client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            # Set up headers and data for token request
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'grant_type': 'client_credentials',
                'scope': 'pins:read,pins:write,boards:read,boards:write'
            }

            # Get access token
            response = requests.post('https://api.pinterest.com/v5/oauth/token', headers=headers, data=data)
            
            if response.status_code != 200:
                print(f"Failed to generate token. Status code: {response.status_code}")
                return None, None

            token_data = response.json()
            access_token = token_data['access_token']

            # Initialize Pinterest SDK Client
            PinterestSDKClient(access_token=access_token)

            # Read and encode image
            with open(image_path, "rb") as img_file:
                encoded_string = base64.b64encode(img_file.read()).decode()

            # Create pin
            pin_create = Pin.create(
                board_id=board_id,
                title=title,
                link=link,
                description=description,
                media_source={
                    "source_type": "image_base64",
                    "content_type": "image/jpeg",  # adjust to image/png if needed
                    "data": encoded_string
                }
            )
            
            return pin_create.id, pin_create.title

        except Exception as e:
            print(f"Error creating pin: {str(e)}")
            return None, None

    def generate(self, seo_keywords):
        """
        Main method to generate a complete blog post
        Args:
            seo_keywords (str): Main topic/keywords for the blog
        Returns:
            str: Path to the generated blog file
        """
        print(f"\nStarting blog generation for topic: {seo_keywords}")
        self.seo_keywords = seo_keywords
        
        # Generate blog content
        use_openai = False
        model_provider = "OpenAI" if use_openai else "Groq"
        print(f"1. Generating blog content using {model_provider} API...")
        mdx_blog = self.generate_blog(seo_keywords, use_openai=use_openai)
        print("✓ Blog content generated successfully")
        
        # Generate slugs
        print("\n2. Processing blog metadata...")
        title_match = re.search(r'^title:\s*(.*)$', mdx_blog, re.MULTILINE)
        if not title_match:
            raise ValueError("Title not found in the blog")
            
        title = title_match.group(1)
        slug = self.generate_slug(title)
        random_suffix = random.randint(1000, 9999)
        image_folder = f"{slug}-{random_suffix}"
        print(f"✓ Title: {title}")
        print(f"✓ Generated slug: {slug}")
        print(f"✓ Image folder: {image_folder}")
        
        # Correct title format
        print("\n3. Correcting blog title...")
        mdx_blog = self.correct_title(mdx_blog)
        print("✓ Blog title corrected")
        
        # Correct date format
        print("\n4. Updating date...")
        mdx_blog = self.correct_date(mdx_blog)
        print("✓ Date updated to today's date")
        
        # Process images
        print("\n5. Processing and downloading images...")
        mdx_blog, paths = self.process_images(mdx_blog, image_folder)
        print("✓ Images processed and downloaded successfully")
        
        # Save the blog
        print("\n6. Saving blog file...")
        filename = self.save_blog(mdx_blog, slug)
        blog_path = os.path.join(self.blog_path, filename)
        print(f"✓ Blog saved successfully at: {blog_path}")
        
        # Open the blog in Chrome
        print("\n7. Opening blog in Google Chrome...")
        blog_url = f"http://localhost:3000/blog/{slug}"
        os.system(f'google-chrome --new-tab "{blog_url}" &>/dev/null &')
        print(f"✓ Opening blog at: {blog_url}")
        
        # Create Pinterest pin
        print("\n8. Creating Pinterest pin...")
        if paths and self.pinterest_board_id and self.url:
            title_match = re.search(r'^title:\s*(.*)$', mdx_blog, re.MULTILINE)
            summary_match = re.search(r'^summary:\s*(.*)$', mdx_blog, re.MULTILINE)
            
            if title_match and summary_match:
                pin_title = title_match.group(1)
                pin_description = summary_match.group(1)
                pin_id, pin_title = self.create_pinterest_pin(
                    paths[0],  # Use the first image
                    pin_title,
                    pin_description,
                    self.url + f"/blog/{slug}",
                    self.pinterest_board_id
                )
                if pin_id:
                    print(f"✓ Pinterest pin created successfully with ID: {pin_id}")
                else:
                    print("✗ Failed to create Pinterest pin")
        else:
            print("✗ Skipping Pinterest pin creation - no images or board ID available")
        
        print("\nBlog generation completed successfully!")
        return blog_path

# Example usage:
if __name__ == "__main__":
    for topic in topics:
        generator = BlogGenerator(website=website)
        blog_path = generator.generate(topic)