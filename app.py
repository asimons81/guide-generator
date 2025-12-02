import streamlit as st
import google.generativeai as genai
import requests
import json
import base64
from PIL import Image
import io
from datetime import datetime
import re

# Page config
st.set_page_config(
    page_title="Tony Reviews Things - Article Generator",
    page_icon="✍️",
    layout="wide"
)

# Initialize session state
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'article_data' not in st.session_state:
    st.session_state.article_data = {}
if 'images' not in st.session_state:
    st.session_state.images = []

# Configure Gemini API
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash-latest')
except Exception as e:
    st.error(f"Error configuring Gemini API: {e}")
    st.stop()

# Helper Functions
def convert_to_webp(image_file):
    """Convert uploaded image to WebP format"""
    try:
        img = Image.open(image_file)
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        output = io.BytesIO()
        img.save(output, format='WEBP', quality=85)
        output.seek(0)
        return output
    except Exception as e:
        st.error(f"Error converting image: {e}")
        return None

def generate_seo_filename(text, index):
    """Generate SEO-friendly filename from text"""
    # Remove special characters and convert to lowercase
    clean_text = re.sub(r'[^\w\s-]', '', text.lower())
    # Replace spaces with hyphens
    clean_text = re.sub(r'[-\s]+', '-', clean_text)
    # Limit length
    clean_text = clean_text[:50]
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"{clean_text}-{timestamp}-{index}.webp"

def call_gemini(prompt):
    """Call Gemini API with error handling"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Gemini API Error: {e}")
        return None

def upload_to_wordpress(image_data, filename, alt_text):
    """Upload image to WordPress Media Library"""
    wp_url = st.secrets["WP_URL"]
    wp_user = st.secrets["WP_USERNAME"]
    wp_pass = st.secrets["WP_APP_PASSWORD"]
    
    headers = {
        'Content-Disposition': f'attachment; filename={filename}',
        'Content-Type': 'image/webp'
    }
    
    try:
        response = requests.post(
            f"{wp_url}/wp-json/wp/v2/media",
            headers=headers,
            data=image_data.getvalue(),
            auth=(wp_user, wp_pass)
        )
        
        if response.status_code == 201:
            media_data = response.json()
            # Update alt text
            requests.post(
                f"{wp_url}/wp-json/wp/v2/media/{media_data['id']}",
                json={'alt_text': alt_text},
                auth=(wp_user, wp_pass)
            )
            return media_data
        else:
            st.error(f"WordPress upload failed: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error uploading to WordPress: {e}")
        return None

def create_wordpress_post(title, content, meta_desc, slug, categories, tags, featured_image_id):
    """Create WordPress post as draft"""
    wp_url = st.secrets["WP_URL"]
    wp_user = st.secrets["WP_USERNAME"]
    wp_pass = st.secrets["WP_APP_PASSWORD"]
    
    post_data = {
        'title': title,
        'content': content,
        'status': 'draft',
        'slug': slug,
        'meta': {
            'description': meta_desc
        },
        'categories': categories,
        'tags': tags,
        'featured_media': featured_image_id
    }
    
    try:
        response = requests.post(
            f"{wp_url}/wp-json/wp/v2/posts",
            json=post_data,
            auth=(wp_user, wp_pass)
        )
        
        if response.status_code == 201:
            return response.json()
        else:
            st.error(f"WordPress post creation failed: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error creating WordPress post: {e}")
        return None

def get_wp_categories():
    """Fetch existing WordPress categories"""
    wp_url = st.secrets["WP_URL"]
    try:
        response = requests.get(f"{wp_url}/wp-json/wp/v2/categories?per_page=100")
        if response.status_code == 200:
            return {cat['name']: cat['id'] for cat in response.json()}
        return {}
    except:
        return {}

def get_wp_tags():
    """Fetch existing WordPress tags"""
    wp_url = st.secrets["WP_URL"]
    try:
        response = requests.get(f"{wp_url}/wp-json/wp/v2/tags?per_page=100")
        if response.status_code == 200:
            return {tag['name']: tag['id'] for tag in response.json()}
        return {}
    except:
        return {}

# Main App
st.title("✍️ Tony Reviews Things - AI Article Generator")
st.markdown("*Powered by Gemini 2.5 Flash*")

# Progress indicator
progress_labels = ["📝 Topic & Keywords", "🎯 Outline & SEO", "✏️ Content Draft", "🖼️ Image Planning", "📤 Upload Images", "🚀 Publish"]
cols = st.columns(len(progress_labels))
for idx, (col, label) in enumerate(zip(cols, progress_labels), 1):
    if idx < st.session_state.step:
        col.success(label)
    elif idx == st.session_state.step:
        col.info(f"**{label}**")
    else:
        col.write(label)

st.divider()

# STEP 1: Topic & Keyword Input
if st.session_state.step == 1:
    st.header("Step 1: Topic & Keyword Input")
    
    with st.form("step1_form"):
        topic = st.text_input("Article Topic", placeholder="e.g., Best Budget Smartphones 2025")
        keyword = st.text_input("Primary Keyword", placeholder="e.g., budget smartphones")
        tone = st.selectbox("Tone", ["Professional", "Casual", "Enthusiastic", "Technical", "Conversational"])
        word_count = st.slider("Target Word Count", 800, 3000, 1500, step=100)
        
        submitted = st.form_submit_button("Generate SEO Strategy")
        
        if submitted and topic and keyword:
            with st.spinner("Generating SEO strategy with Gemini..."):
                prompt = f"""You are an expert SEO content strategist for "Tony Reviews Things," a WordPress review site.

Topic: {topic}
Primary Keyword: {keyword}
Tone: {tone}
Target Length: {word_count} words

Generate a comprehensive SEO strategy in JSON format:

{{
  "title": "SEO-optimized article title (60 chars max, include keyword naturally)",
  "meta_description": "Compelling meta description (150-156 chars, include keyword, add call-to-action)",
  "slug": "url-friendly-slug-with-keyword",
  "focus_keyphrase": "primary keyword phrase",
  "outline": [
    {{
      "heading": "H2 heading text (include keyword variations)",
      "subheadings": ["H3 subheading 1", "H3 subheading 2"],
      "key_points": ["point 1", "point 2"]
    }}
  ],
  "suggested_categories": ["category1", "category2"],
  "suggested_tags": ["tag1", "tag2", "tag3"],
  "internal_linking_opportunities": ["related topic 1", "related topic 2"]
}}

Ensure:
- Title is click-worthy and includes keyword naturally
- Meta description has strong CTA
- Outline has 4-7 main H2 sections
- First H2 includes the keyword
- Natural keyword distribution throughout outline
- Headers are engaging and descriptive"""

                response = call_gemini(prompt)
                
                if response:
                    try:
                        # Extract JSON from response
                        json_match = re.search(r'\{.*\}', response, re.DOTALL)
                        if json_match:
                            seo_data = json.loads(json_match.group())
                            st.session_state.article_data.update(seo_data)
                            st.session_state.article_data['topic'] = topic
                            st.session_state.article_data['keyword'] = keyword
                            st.session_state.article_data['tone'] = tone
                            st.session_state.article_data['word_count'] = word_count
                            st.session_state.step = 2
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error parsing response: {e}")
                        st.code(response)

# STEP 2: Review & Refine SEO Strategy
elif st.session_state.step == 2:
    st.header("Step 2: Review & Refine SEO Strategy")
    
    data = st.session_state.article_data
    
    with st.form("step2_form"):
        st.subheader("Article Metadata")
        title = st.text_input("Title", value=data.get('title', ''), max_chars=60)
        meta_desc = st.text_area("Meta Description", value=data.get('meta_description', ''), max_chars=156)
        slug = st.text_input("URL Slug", value=data.get('slug', ''))
        focus = st.text_input("Focus Keyphrase", value=data.get('focus_keyphrase', ''))
        
        st.subheader("Article Outline")
        outline_text = st.text_area(
            "Outline (editable)", 
            value=json.dumps(data.get('outline', []), indent=2),
            height=300
        )
        
        st.subheader("Categories & Tags")
        col1, col2 = st.columns(2)
        with col1:
            categories = st.text_input("Categories (comma-separated)", 
                                      value=", ".join(data.get('suggested_categories', [])))
        with col2:
            tags = st.text_input("Tags (comma-separated)", 
                                value=", ".join(data.get('suggested_tags', [])))
        
        col1, col2 = st.columns(2)
        with col1:
            back = st.form_submit_button("← Back")
        with col2:
            next_step = st.form_submit_button("Generate Article →")
        
        if back:
            st.session_state.step = 1
            st.rerun()
            
        if next_step:
            # Update session state with refined data
            st.session_state.article_data['title'] = title
            st.session_state.article_data['meta_description'] = meta_desc
            st.session_state.article_data['slug'] = slug
            st.session_state.article_data['focus_keyphrase'] = focus
            st.session_state.article_data['outline'] = json.loads(outline_text)
            st.session_state.article_data['categories'] = [c.strip() for c in categories.split(',')]
            st.session_state.article_data['tags'] = [t.strip() for t in tags.split(',')]
            st.session_state.step = 3
            st.rerun()

# STEP 3: Generate Article Content
elif st.session_state.step == 3:
    st.header("Step 3: Generate Article Content")
    
    if 'content' not in st.session_state.article_data:
        with st.spinner("Generating article with Gemini... This may take a minute."):
            data = st.session_state.article_data
            
            prompt = f"""You are a professional content writer for "Tony Reviews Things."

Write a comprehensive, SEO-optimized article based on this strategy:

Title: {data['title']}
Topic: {data['topic']}
Primary Keyword: {data['keyword']}
Focus Keyphrase: {data['focus_keyphrase']}
Tone: {data['tone']}
Target Word Count: {data['word_count']}

Outline:
{json.dumps(data['outline'], indent=2)}

Requirements:
- Use the EXACT title as H1 (don't include it in the body, WordPress adds it)
- Follow the outline structure with proper H2 and H3 tags
- Include the focus keyphrase in the first paragraph (first 100 words)
- Use the keyword naturally 3-5 times per 500 words (avoid keyword stuffing)
- Write in {data['tone'].lower()} tone
- Add transition words for readability (however, moreover, additionally, etc.)
- Use short paragraphs (2-4 sentences)
- Include bullet points or numbered lists where appropriate
- Add internal linking placeholders like [LINK: related topic name]
- Write a strong conclusion with call-to-action
- Target {data['word_count']} words total

Format as HTML with proper semantic tags (<p>, <h2>, <h3>, <ul>, <strong>, etc.)
Do NOT include <html>, <body>, or <head> tags - just the article content.
"""

            response = call_gemini(prompt)
            
            if response:
                # Clean up response
                content = response.strip()
                # Remove any markdown code blocks if present
                content = re.sub(r'```html\n?', '', content)
                content = re.sub(r'```\n?', '', content)
                st.session_state.article_data['content'] = content
    
    # Display content for review
    data = st.session_state.article_data
    
    st.subheader("Preview")
    st.markdown(f"**Title:** {data['title']}")
    st.markdown(f"**Meta Description:** {data['meta_description']}")
    
    with st.expander("📄 Article Content", expanded=True):
        edited_content = st.text_area(
            "Edit content if needed",
            value=data.get('content', ''),
            height=400
        )
        st.session_state.article_data['content'] = edited_content
    
    # SEO Checklist
    st.subheader("✅ SEO Checklist")
    content = data.get('content', '')
    keyword = data['keyword'].lower()
    
    checks = {
        "Keyword in title": keyword in data['title'].lower(),
        "Keyword in meta description": keyword in data['meta_description'].lower(),
        "Keyword in first paragraph": keyword in content[:500].lower(),
        "Title length (50-60 chars)": 50 <= len(data['title']) <= 60,
        "Meta description length (150-156 chars)": 150 <= len(data['meta_description']) <= 156,
        "Has H2 headings": '<h2>' in content,
        "Has H3 subheadings": '<h3>' in content,
        "Content length appropriate": len(content.split()) >= data['word_count'] * 0.8
    }
    
    cols = st.columns(2)
    for idx, (check, passed) in enumerate(checks.items()):
        with cols[idx % 2]:
            if passed:
                st.success(f"✓ {check}")
            else:
                st.warning(f"⚠ {check}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Outline"):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("Plan Images →"):
            st.session_state.step = 4
            st.rerun()

# STEP 4: Image Planning
elif st.session_state.step == 4:
    st.header("Step 4: Image Planning")
    
    if 'image_plan' not in st.session_state.article_data:
        with st.spinner("Analyzing article and planning image placements..."):
            data = st.session_state.article_data
            
            prompt = f"""Analyze this article and determine optimal image placement for SEO and user engagement.

Article Title: {data['title']}
Article Content: {data['content'][:2000]}... (truncated for brevity)

Create an image plan in JSON format:

{{
  "images": [
    {{
      "position": "featured",
      "placement_description": "Featured image at top of article",
      "prompt": "Photorealistic image prompt for Gemini (detailed, specific, 2-3 sentences)",
      "alt_text": "SEO-optimized alt text with keyword",
      "caption": "Optional caption text"
    }},
    {{
      "position": "after_section",
      "section_heading": "Exact H2 heading text where image should appear after",
      "placement_description": "Why this image goes here",
      "prompt": "Photorealistic image prompt",
      "alt_text": "SEO-optimized alt text",
      "caption": ""
    }}
  ]
}}

Requirements:
- Suggest 3-5 images total (1 featured + 2-4 in-content)
- Prompts must be photorealistic and detailed
- Each alt text must include variations of "{data['keyword']}"
- Place images strategically to break up long text sections
- Featured image should represent the main topic
- In-content images should illustrate specific sections"""

            response = call_gemini(prompt)
            
            if response:
                try:
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        image_plan = json.loads(json_match.group())
                        st.session_state.article_data['image_plan'] = image_plan
                except Exception as e:
                    st.error(f"Error parsing image plan: {e}")
    
    # Display image plan
    if 'image_plan' in st.session_state.article_data:
        plan = st.session_state.article_data['image_plan']
        
        st.info("📋 Review these image prompts. You can edit them before generating images in Gemini.")
        
        for idx, img in enumerate(plan['images'], 1):
            with st.expander(f"🖼️ Image {idx}: {img.get('position', 'Unknown').title()}", expanded=True):
                st.markdown(f"**Placement:** {img.get('placement_description', 'N/A')}")
                if img.get('section_heading'):
                    st.markdown(f"**After Section:** {img['section_heading']}")
                
                st.text_area(f"Prompt for Image {idx}", value=img['prompt'], key=f"prompt_{idx}", height=100)
                st.text_input(f"Alt Text", value=img['alt_text'], key=f"alt_{idx}")
                st.text_input(f"Caption (optional)", value=img.get('caption', ''), key=f"caption_{idx}")
        
        st.divider()
        st.subheader("📝 Copy & Paste These Prompts into Gemini")
        
        for idx, img in enumerate(plan['images'], 1):
            st.code(f"Image {idx}: {img['prompt']}", language="text")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back to Content"):
                st.session_state.step = 3
                st.rerun()
        with col2:
            if st.button("Upload Images →"):
                st.session_state.step = 5
                st.rerun()

# STEP 5: Upload Images
elif st.session_state.step == 5:
    st.header("Step 5: Upload Generated Images")
    
    plan = st.session_state.article_data.get('image_plan', {})
    images_needed = len(plan.get('images', []))
    
    st.info(f"Upload {images_needed} images in the order they were listed in Step 4")
    
    uploaded_files = st.file_uploader(
        "Upload Images",
        type=['png', 'jpg', 'jpeg', 'webp'],
        accept_multiple_files=True,
        key="image_upload"
    )
    
    if uploaded_files:
        if len(uploaded_files) != images_needed:
            st.warning(f"Please upload exactly {images_needed} images (you uploaded {len(uploaded_files)})")
        else:
            st.success(f"✓ All {images_needed} images uploaded!")
            
            # Preview uploaded images
            cols = st.columns(min(3, len(uploaded_files)))
            for idx, (col, file) in enumerate(zip(cols, uploaded_files)):
                with col:
                    st.image(file, caption=f"Image {idx+1}", use_container_width=True)
            
            st.session_state.images = uploaded_files
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Image Plan"):
            st.session_state.step = 4
            st.rerun()
    with col2:
        if st.button("Publish to WordPress →", disabled=len(uploaded_files) != images_needed):
            st.session_state.step = 6
            st.rerun()

# STEP 6: Publish to WordPress
elif st.session_state.step == 6:
    st.header("Step 6: Publish to WordPress")
    
    if st.button("🚀 Upload Draft to WordPress"):
        with st.spinner("Processing and uploading to WordPress..."):
            data = st.session_state.article_data
            plan = data['image_plan']
            uploaded_images = st.session_state.images
            
            # Convert and upload images
            st.write("Converting images to WebP...")
            wp_images = []
            
            for idx, (img_file, img_data) in enumerate(zip(uploaded_images, plan['images']), 1):
                with st.spinner(f"Processing image {idx}..."):
                    # Convert to WebP
                    webp_data = convert_to_webp(img_file)
                    if webp_data:
                        # Generate SEO filename
                        filename = generate_seo_filename(img_data['alt_text'], idx)
                        
                        # Upload to WordPress
                        media = upload_to_wordpress(webp_data, filename, img_data['alt_text'])
                        
                        if media:
                            wp_images.append({
                                'id': media['id'],
                                'url': media['source_url'],
                                'alt': img_data['alt_text'],
                                'caption': img_data.get('caption', ''),
                                'position': img_data.get('position'),
                                'section_heading': img_data.get('section_heading')
                            })
                            st.success(f"✓ Image {idx} uploaded: {filename}")
                        else:
                            st.error(f"Failed to upload image {idx}")
            
            # Insert images into content
            content = data['content']
            
            # Set featured image
            featured_image_id = wp_images[0]['id'] if wp_images else 0
            
            # Insert in-content images
            for img in wp_images[1:]:  # Skip featured image
                if img.get('section_heading'):
                    # Find the section heading and insert image after it
                    heading_pattern = f"<h2>.*?{re.escape(img['section_heading'])}.*?</h2>"
                    match = re.search(heading_pattern, content, re.IGNORECASE)
                    
                    if match:
                        insert_pos = match.end()
                        img_html = f'\n<figure class="wp-block-image"><img src="{img["url"]}" alt="{img["alt"]}" />'
                        if img['caption']:
                            img_html += f'<figcaption>{img["caption"]}</figcaption>'
                        img_html += '</figure>\n'
                        
                        content = content[:insert_pos] + img_html + content[insert_pos:]
            
            # Get or create categories and tags
            wp_categories = get_wp_categories()
            wp_tags = get_wp_tags()
            
            category_ids = []
            for cat in data.get('categories', []):
                if cat in wp_categories:
                    category_ids.append(wp_categories[cat])
            
            tag_ids = []
            for tag in data.get('tags', []):
                if tag in wp_tags:
                    tag_ids.append(wp_tags[tag])
            
            # Create WordPress post
            st.write("Creating WordPress draft post...")
            post = create_wordpress_post(
                title=data['title'],
                content=content,
                meta_desc=data['meta_description'],
                slug=data['slug'],
                categories=category_ids,
                tags=tag_ids,
                featured_image_id=featured_image_id
            )
            
            if post:
                st.success("✅ Article published as DRAFT on WordPress!")
                st.balloons()
                
                st.subheader("Post Details")
                st.write(f"**Title:** {post['title']['rendered']}")
                st.write(f"**Status:** {post['status']}")
                st.write(f"**Edit URL:** {post['link'].replace('?preview=true', '')}")
                
                if st.button("🔄 Start New Article"):
                    # Reset session state
                    st.session_state.step = 1
                    st.session_state.article_data = {}
                    st.session_state.images = []
                    st.rerun()
            else:
                st.error("Failed to create WordPress post. Check your credentials and try again.")

# Sidebar
with st.sidebar:
    st.header("About")
    st.write("This app generates SEO-optimized articles for Tony Reviews Things using Gemini 2.5 Flash.")
    
    st.divider()
    
    st.header("Setup")
    st.markdown("""
    **Required Secrets:**
    - `GEMINI_API_KEY`
    - `WP_URL` (e.g., https://yoursite.com)
    - `WP_USERNAME`
    - `WP_APP_PASSWORD`
    
    Configure in Streamlit Cloud: Settings → Secrets
    """)
    
    st.divider()
    
    if st.button("🔄 Reset App"):
        st.session_state.step = 1
        st.session_state.article_data = {}
        st.session_state.images = []
        st.rerun()
