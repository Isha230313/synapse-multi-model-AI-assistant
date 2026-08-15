<script>
  import { createEventDispatcher } from 'svelte';
  // export let onSearch;

  export let loading = false;  // Loading state from parent

  // ============================================
  // Component State
  // ============================================
  const dispatch = createEventDispatcher();  // Send events to parent
  let searchQuery= '';  // Current search input value
  let wasLoading = false;  // Track previous loading state

  // ============================================
  // Reactive Statement: Clear input when loading completes
  // ============================================
  $: {
    // When loading changes from true to false, clear the input
    if (wasLoading && !loading && searchQuery.trim()) {
      searchQuery = '';
    }
    wasLoading = loading;
  }

  // ============================================
  // Event Handlers
  // ============================================
  /**
   * Submit search query (called by button click or Enter key)
   */
  function handleSubmit(event) {
    event.preventDefault();
    if (searchQuery.trim()) {
      dispatch('search', searchQuery.trim());
    }
  }

  /**
   * Handle Enter key press in search input
   */
  function handleKeyPress(event) {
    if (event.key === 'Enter') {
      handleSubmit();
    }
  }
</script>

<div class="search-container">
  <div class="search-box">
    <span class="search-icon">🔍</span>
    <input
      type="text"
      class="search-input"
      placeholder="Ask me anything..."
      bind:value={searchQuery}
      on:keypress={handleKeyPress}
      disabled={loading}
    />
    <button
      class="search-button"
      on:click={handleSubmit}
      disabled={loading || !searchQuery.trim()}
    >
      {#if loading}
        <span class="spinner"></span>
        Searching...
      {:else}
        Search
      {/if}
    </button>
  </div>
</div>

<style>
  /* Search bar container - wider, centered */
  .search-container {
    width: 85%;
    max-width: 900px;
    margin: 0.5rem auto 1rem;
    animation: fadeInUp 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.2s both;
    position: relative;
  }

  .search-container::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 120%;
    height: 120%;
    background: radial-gradient(
      circle,
      rgba(99, 102, 241, 0.1) 0%,
      transparent 70%
    );
    transform: translate(-50%, -50%);
    z-index: -1;
    animation: glowPulse 3s ease-in-out infinite;
    pointer-events: none;
  }

  @keyframes glowPulse {
    0%, 100% { opacity: 0.5; transform: translate(-50%, -50%) scale(1); }
    50% { opacity: 0.8; transform: translate(-50%, -50%) scale(1.1); }
  }

  /* Search box with glassmorphism effect */

  .search-box {
    display: flex;
    align-items: center;
    background: rgba(20, 20, 30, 0.95);
    border-radius: 12px;
    padding: 0.75rem 1.5rem;
    box-shadow: 
      0 8px 32px rgba(0, 0, 0, 0.6),
      0 0 0 1px rgba(99, 102, 241, 0.3),
      0 0 40px rgba(99, 102, 241, 0.15),
      inset 0 1px 0 rgba(255, 255, 255, 0.1);
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    backdrop-filter: blur(20px);
    border: 2px solid rgba(139, 92, 246, 0.4);
    width: 100%;
    position: relative;
    overflow: hidden;
  }

  .search-box::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(99, 102, 241, 0.2),
      transparent
    );
    transition: left 0.6s ease;
  }

  .search-box:hover::before {
    left: 100%;
  }

  .search-box:focus-within {
    box-shadow: 
      0 12px 48px rgba(99, 102, 241, 0.6),
      0 0 0 2px rgba(99, 102, 241, 0.5),
      0 0 80px rgba(99, 102, 241, 0.4),
      inset 0 1px 0 rgba(255, 255, 255, 0.2);
    transform: translateY(-3px) scale(1.01);
    border-color: rgba(99, 102, 241, 0.8);
    background: rgba(25, 25, 35, 0.98);
  }

  .search-icon {
    font-size: 1.5rem;
    margin: 0 1rem 0 0;
    opacity: 0.8;
    transition: all 0.3s ease;
    filter: drop-shadow(0 0 8px rgba(99, 102, 241, 0.6));
    animation: iconPulse 2s ease-in-out infinite;
  }

  .search-box:focus-within .search-icon {
    opacity: 1;
    transform: scale(1.1) rotate(5deg);
    filter: drop-shadow(0 0 12px rgba(99, 102, 241, 1));
  }

  @keyframes iconPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
  }

  .search-input {
    flex: 1;
    border: none;
    outline: none;
    font-size: 1rem;
    padding: 0.5rem 0.75rem;
    background: transparent;
    color: #ffffff;
    font-weight: 500;
    min-width: 0;
    transition: all 0.3s ease;
    letter-spacing: 0.3px;
  }

  .search-input::placeholder {
    color: rgba(255, 255, 255, 0.4);
    font-weight: 400;
    transition: all 0.3s ease;
  }

  .search-box:focus-within .search-input::placeholder {
    color: rgba(255, 255, 255, 0.6);
    transform: translateX(5px);
  }

  .search-input:focus {
    color: #ffffff;
    text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
  }

  .search-input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .search-button {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #ec4899 100%);
    background-size: 200% 200%;
    color: white;
    border: none;
    padding: 0.625rem 2rem;
    border-radius: 10px;
    font-size: 0.95rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    align-items: center;
    gap: 0.5rem;
    white-space: nowrap;
    box-shadow: 
      0 4px 16px rgba(99, 102, 241, 0.5),
      0 0 20px rgba(99, 102, 241, 0.3),
      inset 0 1px 0 rgba(255, 255, 255, 0.2);
    margin-left: 1.25rem;
    flex-shrink: 0;
    position: relative;
    overflow: hidden;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    animation: gradientShift 3s ease infinite;
  }

  .search-button::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.3),
      transparent
    );
    transition: left 0.5s ease;
  }

  .search-button:hover:not(:disabled)::before {
    left: 100%;
  }

  .search-button:hover:not(:disabled) {
    transform: translateY(-3px) scale(1.05);
    box-shadow: 
      0 8px 24px rgba(99, 102, 241, 0.7),
      0 0 40px rgba(99, 102, 241, 0.5),
      inset 0 1px 0 rgba(255, 255, 255, 0.3);
    animation: gradientShift 1.5s ease infinite;
  }

  .search-button:active:not(:disabled) {
    transform: translateY(-1px) scale(1.02);
  }

  .search-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
    animation: none;
  }

  @keyframes gradientShift {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (max-width: 768px) {
    .search-container {
      max-width: 98%;
    }

    .search-box {
      padding: 1rem;
    }

    .search-input {
      font-size: 1rem;
    }
  }
</style>


