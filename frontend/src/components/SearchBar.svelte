<script>
  import { createEventDispatcher } from 'svelte';

  // Component Props
  export let loading = false;

  // Component State
  const dispatch = createEventDispatcher();
  let searchQuery = '';

  // Event Handlers
  function handleSubmit() {
    if (searchQuery.trim() && !loading) {
      dispatch('search', searchQuery);
      searchQuery = '';
    }
  }

  function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }
</script>

<!-- Centered Search UI -->
<div class="flex flex-col items-center justify-center min-h-[70vh] w-full px-4 sm:px-6 lg:px-8 py-12">
  <div class="w-full max-w-2xl mx-auto text-center space-y-8">
    
    <!-- Title -->
    <div class="space-y-3">
      <h1 class="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight" style="background: linear-gradient(135deg, #8b5cf6, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
        Synapse
      </h1>

      <!-- Tagline -->
      <p class="text-lg sm:text-xl text-gray-600 dark:text-gray-300 font-light">
        Where curiosity meets intelligence
      </p>
    </div>

    <!-- Search Container -->
    <div class="w-full">
      <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-0 bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 focus-within:border-indigo-500 dark:focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-500/20 dark:focus-within:ring-indigo-400/20 transition-all duration-300 overflow-hidden">
        
        <!-- Search Input -->
        <input
          type="text"
          bind:value={searchQuery}
          on:keypress={handleKeyPress}
          disabled={loading}
          placeholder="Type your question here..."
          autofocus
          class="flex-1 px-6 py-4 sm:py-5 bg-transparent text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 text-base sm:text-lg font-normal outline-none border-none disabled:opacity-50 disabled:cursor-not-allowed"
        />
        
        <!-- Search Button -->
        <button
          on:click={handleSubmit}
          disabled={loading || !searchQuery.trim()}
          class="px-6 sm:px-8 py-4 sm:py-5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-semibold text-base sm:text-lg transition-all duration-200 flex items-center justify-center gap-2 min-w-[120px] sm:min-w-[140px] hover:shadow-md disabled:shadow-none"
        >
          {#if loading}
            <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Searching</span>
          {:else}
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
            <span>Search</span>
          {/if}
        </button>
      </div>
    </div>

    <!-- Helper Text -->
    <p class="text-sm text-gray-500 dark:text-gray-400">
      Press <kbd class="px-2 py-1 mx-1 text-xs font-semibold text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded">Enter</kbd> to search
    </p>
  </div>
</div>
