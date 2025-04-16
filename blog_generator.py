import os
import re
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from google_images_search import GoogleImagesSearch
from utils import anycode_prompt, moroccoheritage_prompt, user_prompt
from ignore import website, topics 

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
        elif self.website == 2:
            self.system_prompt = anycode_prompt
            self.blog_path = "/home/adil/repo/gobitcode/data/blog/"
            self.image_path = "/home/adil/repo/gobitcode/public/static/images"
        else:
            raise ValueError("Invalid website configuration")

    def load_environment(self):
        """Load environment variables and API keys"""
        load_dotenv()
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        self.google_cx = os.getenv('GOOGLE_CX')



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
            str: New filename of the downloaded image
        """
        gis = GoogleImagesSearch(self.google_api_key, self.google_cx)
        
        search_params = {
            'q': keyword,
            'num': limit,
            'safe': 'off',
        }

        gis.search(search_params=search_params)
        image = gis.results()[0]
        image.download(path)
        
        # Rename the downloaded image
        old_image_name = os.path.basename(image.path)
        filename, extension = os.path.splitext(old_image_name)
        new_image_name = f"{self.generate_slug(filename)}{extension}"
        os.rename(image.path, os.path.join(path, new_image_name))
        
        return new_image_name

    def generate_blog(self, seo_keywords):
        """
        Generate a blog post using Groq API
        Args:
            seo_keywords (str): Main topic/keywords for the blog
        Returns:
            str: Generated blog content
        """
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
            temperature=1,
            max_tokens=1024*4,
            top_p=1,
            stream=False,
            stop=None,
        )

        return completion.choices[0].message.content

    def process_images(self, mdx_blog, parent_folder):
        """
        Process and download images for the blog
        Args:
            mdx_blog (str): Blog content with image tags
            parent_folder (str): Folder to save images
        Returns:
            str: Updated blog content with new image paths
        """
        img_tag_regex = r'<img[^>]*alt=\"([^\"]*)\"[^>]*>'
        matches = re.findall(img_tag_regex, mdx_blog)
        
        for match in matches:
            image_name = self.download_images(
                f"{self.seo_keywords} {match}",
                os.path.join(self.image_path, parent_folder)
            )
            new_src = f'/static/images/{parent_folder}/{image_name}'
            mdx_blog = re.sub(
                rf'(<img[^>]*src=\")[^\"]*(\"[^>]*alt=\"{re.escape(match)}\"[^>]*>)',
                rf'\1{new_src}\2',
                mdx_blog
            )
        
        return mdx_blog

    def correct_title(self, mdx_blog):
        """Remove colon from the title line"""
        title_regex = r'^(title:.*?):(.*)$'
        return re.sub(title_regex, r'\1\2', mdx_blog, flags=re.MULTILINE)

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
        print("1. Generating blog content using Groq API...")
        mdx_blog = self.generate_blog(seo_keywords)
        print("✓ Blog content generated successfully")
        
        # Generate slugs
        print("\n2. Processing blog metadata...")
        title_match = re.search(r'^title:\s*(.*)$', mdx_blog, re.MULTILINE)
        if not title_match:
            raise ValueError("Title not found in the blog")
            
        title = title_match.group(1)
        slug = self.generate_slug(title)
        parent_folder = self.generate_slug(seo_keywords)
        print(f"✓ Title: {title}")
        print(f"✓ Generated slug: {slug}")
        print(f"✓ Parent folder: {parent_folder}")
        
        # Process images
        print("\n3. Processing and downloading images...")
        mdx_blog = self.process_images(mdx_blog, parent_folder)
        print("✓ Images processed and downloaded successfully")
        
        # Correct title format
        print("\n4. Correcting blog title...")
        mdx_blog = self.correct_title(mdx_blog)
        print("✓ Blog title corrected")
        
        # Correct date format
        print("\n5. Updating date...")
        mdx_blog = self.correct_date(mdx_blog)
        print("✓ Date updated to today's date")
        
        # Save the blog
        print("\n6. Saving blog file...")
        filename = self.save_blog(mdx_blog, slug)
        blog_path = os.path.join(self.blog_path, filename)
        print(f"✓ Blog saved successfully at: {blog_path}")
        
        print("\nBlog generation completed successfully!")
        return blog_path

# Example usage:
if __name__ == "__main__":
    for topic in topics:
        generator = BlogGenerator(website=website)
        blog_path = generator.generate(topic)