<script>
  export let person;
  export let generatePDF;

  // Helper function to extract source information from URL
  function getSourceInfo(url, personName, index) {
    if (!url) return { name: 'Source', title: 'Unknown' };
    
    // Check if this URL matches any news item (use news title if available)
    let newsTitle = null;
    if (person.news && Array.isArray(person.news)) {
      const matchingNews = person.news.find(item => {
        if (typeof item === 'object' && item.url) {
          return item.url === url || item.url.includes(url) || url.includes(item.url);
        }
        return false;
      });
      if (matchingNews && matchingNews.title) {
        newsTitle = matchingNews.title;
      }
    }
    
    try {
      const urlObj = new URL(url);
      const domain = urlObj.hostname.replace('www.', '').toLowerCase();
      const path = urlObj.pathname;
      
      // Extract source name based on domain
      let sourceName = 'Source';
      let title = newsTitle || `${personName} Profile`;
      
      // Wikipedia
      if (domain.includes('wikipedia.org')) {
        sourceName = 'Wikipedia';
        if (!newsTitle) {
          const pageName = path.split('/').pop()?.replace(/_/g, ' ') || personName;
          title = pageName;
        }
      }
      // News sites
      else if (domain.includes('nytimes.com')) {
        sourceName = 'New York Times';
        if (!newsTitle) title = `${personName}'s Latest`;
      }
      else if (domain.includes('wsj.com') || domain.includes('wallstreetjournal')) {
        sourceName = 'Wall Street Journal';
        if (!newsTitle) title = 'Business Moves';
      }
      else if (domain.includes('bbc.com')) {
        sourceName = 'BBC';
        if (!newsTitle) title = `${personName}'s Latest`;
      }
      else if (domain.includes('cnn.com')) {
        sourceName = 'CNN';
        if (!newsTitle) title = `${personName}'s Latest`;
      }
      else if (domain.includes('reuters.com')) {
        sourceName = 'Reuters';
        if (!newsTitle) title = `${personName}'s Latest`;
      }
      else if (domain.includes('forbes.com')) {
        sourceName = 'Forbes';
        if (!newsTitle) title = `${personName}'s Latest`;
      }
      else if (domain.includes('bloomberg.com')) {
        sourceName = 'Bloomberg';
        if (!newsTitle) title = `${personName}'s Latest`;
      }
      else if (domain.includes('theguardian.com')) {
        sourceName = 'The Guardian';
        if (!newsTitle) title = `${personName}'s Latest`;
      }
      // Companies/Organizations
      else if (domain.includes('tesla.com')) {
        sourceName = 'Tesla Inc.';
        if (!newsTitle) title = `${personName} Profile`;
      }
      else if (domain.includes('spacex.com') || domain.includes('spacex')) {
        sourceName = 'Space Exploration Technologies Corp.';
        if (!newsTitle) title = 'Leadership';
      }
      // Social media
      else if (domain.includes('linkedin.com')) {
        sourceName = 'LinkedIn';
        if (!newsTitle) title = 'Professional Profile';
      }
      else if (domain.includes('twitter.com') || domain.includes('x.com')) {
        sourceName = 'Twitter/X';
        if (!newsTitle) title = 'Profile';
      }
      else if (domain.includes('instagram.com')) {
        sourceName = 'Instagram';
        if (!newsTitle) title = `${personName} Profile`;
      }
      else if (domain.includes('facebook.com')) {
        sourceName = 'Facebook';
        if (!newsTitle) title = `${personName} Profile`;
      }
      else if (domain.includes('youtube.com')) {
        sourceName = 'YouTube';
        if (!newsTitle) title = `${personName}`;
      }
      // Generic - extract domain name
      else {
        const domainParts = domain.split('.');
        if (domainParts.length >= 2) {
          const mainDomain = domainParts[domainParts.length - 2];
          sourceName = mainDomain.replace(/-/g, ' ').replace(/_/g, ' ')
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
          // Add Corp./Inc. for business domains
          if (mainDomain.includes('tech') || mainDomain.includes('corp') || mainDomain.includes('company')) {
            if (!sourceName.toLowerCase().includes('corp') && !sourceName.toLowerCase().includes('inc')) {
              sourceName += ' Corp.';
            }
          }
        }
        if (!newsTitle) title = `${personName} Profile`;
      }
      
      return { name: sourceName, title };
    } catch (e) {
      return { name: 'Source', title: newsTitle || 'Unknown' };
    }
  }
</script>

<div class="person-card">
  <div class="card-header">
    <h3 class="person-name">{person.name}</h3>
    <span class="source-badge" class:cache={person.source === 'cache'}>
      {person.source === 'cache' ? '⚡ Cached' : '🤖 AI'}
    </span>
  </div>

  {#if person.bio}
    <section class="bio-section">
      <h3 class="section-header">
        <span class="section-icon">📖</span>
        Biography
      </h3>
      <p class="bio-text">{person.bio}</p>
    </section>
  {/if}

  {#if person.news && person.news.length > 0}
    <section class="news-section">
      <h3 class="section-header">
        <span class="section-icon">📰</span>
        Latest News
      </h3>
      <div class="news-grid">
        {#each person.news as item}
          <a href={item.url} target="_blank" rel="noopener noreferrer" class="news-item">
            <div class="news-content">
              <h4 class="news-title">{item.title}</h4>
              {#if item.summary}
                <p class="news-summary">{item.summary}</p>
              {/if}
            </div>
            <span class="news-link">→</span>
          </a>
        {/each}
      </div>
    </section>
  {/if}

  {#if person.images && person.images.length > 0}
    <section class="images-section">
      <h3 class="section-header">
        <span class="section-icon">🖼️</span>
        Images
      </h3>
      <div class="images-grid">
        {#each person.images as imageUrl}
          <div class="image-wrapper">
            <img src={imageUrl} alt={person.name} class="person-image" loading="lazy" />
          </div>
        {/each}
      </div>
    </section>
  {/if}

  {#if person.sources && person.sources.length > 0}
    <section class="references-section">
      <h3 class="section-header">
        <span class="section-icon">📚</span>
        References
      </h3>
      <div class="references-list">
        {#each person.sources as source, index}
          {@const sourceInfo = getSourceInfo(source, person.name, index + 1)}
          <div class="reference-item">
            <span class="reference-number">[{index + 1}]</span>
            <span class="reference-content">
              <strong>{sourceInfo.name}</strong>. <em>{sourceInfo.title}</em>
            </span>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  <button class="generate-pdf-btn" on:click={() => generatePDF(person.name)}>
    📄 Generate PDF
  </button>

  
</div>

<style>
  .person-card {
    background: rgba(30, 30, 40, 0.8);
    border-radius: 16px;
    padding: 1.5rem;
    margin-top: 1rem;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 30px rgba(139, 92, 246, 0.2);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(139, 92, 246, 0.3);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 2px solid rgba(99, 102, 241, 0.3);
  }

  .person-name {
    font-size: 1.5rem;
    font-weight: 700;
    color: #ffffff;
    margin: 0;
    text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
  }

  .source-badge {
    background: linear-gradient(135deg, var(--accent) 0%, #f472b6 100%);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    font-size: 0.875rem;
    font-weight: 600;
    box-shadow: 0 4px 12px rgba(236, 72, 153, 0.3);
  }

  .source-badge.cache {
    background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
  }

  .bio-section,
  .news-section,
  .images-section,
  .references-section {
    margin-bottom: 1.5rem;
  }

  .bio-section:last-child,
  .news-section:last-child,
  .images-section:last-child,
  .references-section:last-child {
    margin-bottom: 0;
  }

  .section-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 1.5rem;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 1.25rem;
    text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
  }

  .section-icon {
    font-size: 1.75rem;
  }

  .bio-text {
    font-size: 1rem;
    line-height: 1.6;
    color: rgba(255, 255, 255, 0.9);
    background: rgba(99, 102, 241, 0.15);
    padding: 1rem;
    border-radius: 8px;
    border-left: 3px solid #6366f1;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
  }

  .news-grid {
    display: grid;
    gap: 1rem;
  }

  .news-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(99, 102, 241, 0.15);
    padding: 1.25rem 1.5rem;
    border-radius: 12px;
    text-decoration: none;
    color: rgba(255, 255, 255, 0.9);
    transition: all 0.3s ease;
    border: 2px solid transparent;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
  }

  .news-item:hover {
    background: rgba(99, 102, 241, 0.25);
    border-color: #6366f1;
    transform: translateX(4px);
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4), 0 0 30px rgba(99, 102, 241, 0.2);
  }

  .news-content {
    flex: 1;
  }

  .news-title {
    font-size: 1.125rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
    color: #ffffff;
  }

  .news-summary {
    font-size: 0.9375rem;
    color: rgba(255, 255, 255, 0.7);
    line-height: 1.6;
  }

  .news-link {
    font-size: 1.5rem;
    color: #6366f1;
    margin-left: 1rem;
    transition: transform 0.3s ease;
  }

  .news-item:hover .news-link {
    transform: translateX(4px);
  }

  .images-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1.5rem;
  }

  .image-wrapper {
    position: relative;
    border-radius: 12px;
    overflow: hidden;
    aspect-ratio: 1;
    box-shadow: 0 4px 12px var(--shadow);
    transition: all 0.3s ease;
  }

  .image-wrapper:hover {
    transform: scale(1.05);
    box-shadow: 0 8px 24px var(--shadow-lg);
  }

  .person-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(30px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (max-width: 768px) {
    .person-card {
      padding: 1.5rem;
    }

    .card-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 1rem;
    }

    .person-name {
      font-size: 1.75rem;
    }

    .section-header {
      font-size: 1.25rem;
    }

    .bio-text {
      font-size: 1rem;
      padding: 1rem;
    }

    .images-grid {
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      gap: 1rem;
    }
  }

  .references-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .reference-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.875rem 1rem;
    background: rgba(99, 102, 241, 0.1);
    border-radius: 8px;
    border-left: 3px solid #6366f1;
    transition: all 0.2s ease;
  }

  .reference-item:hover {
    background: rgba(99, 102, 241, 0.15);
    transform: translateX(2px);
  }

  .reference-number {
    color: #6366f1;
    font-weight: 600;
    font-size: 0.9375rem;
    flex-shrink: 0;
  }

  .reference-content {
    flex: 1;
    font-size: 0.9375rem;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.9);
  }

  .reference-content strong {
    color: #ffffff;
    font-weight: 600;
  }

  .reference-content em {
    color: rgba(255, 255, 255, 0.75);
    font-style: italic;
  }

  .generate-pdf-btn {
    background: #6366f1;
    color: white;
    padding: 0.7rem 1.2rem;
    border-radius: 8px;
    border: none;
    cursor: pointer;
    margin-top: 1rem;
    font-size: 0.9375rem;
    font-weight: 600;
    width: 100%;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
  }
  
  .generate-pdf-btn:hover {
    background: #4f46e5;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
  }
  
  .generate-pdf-btn:active {
    transform: translateY(0);
  }

</style>


