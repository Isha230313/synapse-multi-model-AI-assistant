<script>
  import SearchBox from './components/SearchBox.svelte';
  import { onMount } from 'svelte';
  import PersonCard from './components/PersonCard.svelte';



  // ============================================
  // Configuration
  // ============================================
  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  // Get token from environment - Vite only loads .env on startup!
  const API_BEARER_TOKEN = import.meta.env.VITE_API_BEARER_TOKEN || '';

  // Helper function to get headers with authentication
  function getAuthHeaders() {
    const headers = { "Content-Type": "application/json" };
    const token = import.meta.env.VITE_API_BEARER_TOKEN;
    if (token && token.trim()) {
      headers["Authorization"] = `Bearer ${token.trim()}`;
    }
    return headers;
  }

  // ============================================
  // State Variables
  // ============================================
  let chatMessages = [];  // Array of chat messages (user, assistant, error)
  let loading = false;    // Loading state for search operations
  let error = '';         // Error message if any
  let menuOpen = false;   // Three-dot menu state
  let showHistory = false; // Chat history panel state
  let chatHistory = [];   // Array of saved chat sessions
  function getTodaySessionId() {
    const d = new Date();
    return d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate(); // YYYYMMDD
  }
  let currentSessionId = getTodaySessionId();
  let hasStartedChatting = false; // Landing page state
  
  // Email modal state
  let showEmailModal = false;
  let emailAddress = '';
  let emailSending = false;
  let emailStatus = ''; // 'success' | 'error' | ''
  let emailStatusMessage = '';
  let emailSendType = 'text'; // 'text' | 'pdf'
  let emailTargetPersonName = '';

  // LLM Provider selection
  let currentProvider = 'gemini'; // Default provider
  let availableProviders = ['openai', 'gemini']; // Available providers
  let providerLoading = false; // Loading state for provider operations

  // Background is now handled by CSS with image file

  // ============================================
  // Lifecycle
  // ============================================
  // ============================================
  // LocalStorage Functions
  // ============================================
  /**
   * Save chat messages to localStorage
   */
  function saveChatToStorage() {
    try {
      const messagesToSave = chatMessages.map(msg => ({
        type: msg.type,
        content: msg.content,
        timestamp: msg.timestamp.toISOString(),
        // Preserve person data for PersonCard component
        person: msg.person || null,
        // Preserve PDF generation flags
        pdfGenerated: msg.pdfGenerated || false,
        pdfType: msg.pdfType || null
      }));
      localStorage.setItem('chatMessages', JSON.stringify(messagesToSave));
    } catch (err) {
      // save failed silently
    }
  }

  /**
   * Load chat messages from localStorage
   */
  function loadChatFromStorage() {
    try {
      const saved = localStorage.getItem('chatMessages');
      if (saved) {
        const parsed = JSON.parse(saved);
        chatMessages = parsed.map(msg => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
          // Ensure person data is preserved when loading from storage
          person: msg.person || null,
          pdfGenerated: msg.pdfGenerated || false,
          pdfType: msg.pdfType || null
        }));
        }
    } catch (err) {
      // load failed silently
    }
  }

  // ============================================
  // Lifecycle
  // ============================================
  onMount(async () => {
    // Check if user has existing chat messages (refresh scenario)
    const savedMessages = localStorage.getItem('chatMessages');
    if (savedMessages) {
      try {
        const parsed = JSON.parse(savedMessages);
        if (parsed && parsed.length > 0) {
          // User has chat messages - they were chatting, restore chat view
          hasStartedChatting = true;
          loadChatFromStorage();
          
          // Restore scroll position after messages load
          setTimeout(() => {
            const chatContainer = document.querySelector('.chat-messages');
            if (chatContainer) {
              const savedScrollPosition = localStorage.getItem('chatScrollPosition');
              if (savedScrollPosition !== null) {
                chatContainer.scrollTop = parseInt(savedScrollPosition, 10);
                localStorage.removeItem('chatScrollPosition');
              } else {
                chatContainer.scrollTop = chatContainer.scrollHeight;
              }
            }
          }, 200);
        } else {
          // No messages - fresh start, show landing page
          hasStartedChatting = false;
        }
      } catch (err) {
        hasStartedChatting = false;
      }
    } else {
      // No saved messages - fresh start, show landing page
      hasStartedChatting = false;
    }
    
    // Load current provider status
    await loadProviderStatus();
    
    // Save scroll position before page unload
    const handleBeforeUnload = () => {
      // Save chat to history
      if (chatMessages.length > 0) {
        const hasAssistantResponse = chatMessages.some(msg => 
          msg.type === 'assistant' || msg.type === 'error'
        );
        const hasUserMessage = chatMessages.some(msg => msg.type === 'user');
        if (hasUserMessage && hasAssistantResponse) {
          saveChatToHistory();
        }
      }
      
      // Save scroll position
      if (hasStartedChatting) {
        const chatContainer = document.querySelector('.chat-messages');
        if (chatContainer) {
          localStorage.setItem('chatScrollPosition', chatContainer.scrollTop.toString());
        }
      }
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    // Cleanup on component destroy
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  });
  
  /**
   * Load current LLM provider status
   */
  async function loadProviderStatus() {
    try {
      const response = await fetch(`${API_BASE_URL}/llm/provider/status`, {
        headers: getAuthHeaders()
      });
      
      if (response.ok) {
        const data = await response.json();
        currentProvider = data.current_provider || 'gemini';
        availableProviders = data.available_providers || ['openai', 'gemini'];
      }
    } catch (err) {
      // provider status unavailable, keep default
    }
  }
  
  /**
   * Switch LLM provider
   */
  async function switchProvider(newProvider) {
    if (providerLoading || newProvider === currentProvider) return;

    const oldProvider = currentProvider;
    providerLoading = true;

    try {
      const response = await fetch(`${API_BASE_URL}/llm/provider/switch`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ provider: newProvider })
      });
      
      if (response.ok) {
        const data = await response.json();
        currentProvider = data.current_provider || newProvider;

        // Show success message
        chatMessages = [...chatMessages, {
          type: 'assistant',
          content: `Switched to ${currentProvider.toUpperCase()} provider.`,
          timestamp: new Date()
        }];
        saveChatToStorage();
      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to switch provider (${response.status})`);
      }
    } catch (err) {
      error = `Failed to switch provider: ${err.message}`;
      // Revert dropdown to old provider on error
      currentProvider = oldProvider;
    } finally {
      providerLoading = false;
    }
  }

  /**
   * Start chatting - navigate to chat interface
   */
  function startChatting() {
    hasStartedChatting = true;
    localStorage.setItem('hasStartedChatting', 'true');
    // Load chat from localStorage when starting
    loadChatFromStorage();
    
    // Restore scroll position after loading messages
    setTimeout(() => {
      const chatContainer = document.querySelector('.chat-messages');
      if (chatContainer) {
        const savedScrollPosition = localStorage.getItem('chatScrollPosition');
        if (savedScrollPosition !== null) {
          chatContainer.scrollTop = parseInt(savedScrollPosition, 10);
          localStorage.removeItem('chatScrollPosition');
        } else {
          chatContainer.scrollTop = chatContainer.scrollHeight;
        }
      }
    }, 200);
  }

  /**
   * Go back to main/landing page
   */
  function goBackToMain() {
    // Save scroll position before leaving chat
    const chatContainer = document.querySelector('.chat-messages');
    if (chatContainer) {
      localStorage.setItem('chatScrollPosition', chatContainer.scrollTop.toString());
    }
    
    hasStartedChatting = false;
    localStorage.removeItem('hasStartedChatting');
  }

  /**
   * Convert base64 string to Blob
   */
  function base64ToBlob(base64, mimeType) {
    try {
      if (!base64 || typeof base64 !== 'string') {
        throw new Error("Invalid base64 data: must be a non-empty string");
      }
      
      // Remove data URL prefix if present (e.g., "data:application/pdf;base64,")
      const base64Data = base64.includes(',') ? base64.split(',')[1] : base64;
      
      // Decode base64 string
      const byteCharacters = atob(base64Data);
      const byteNumbers = new Array(byteCharacters.length);
      
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: mimeType || "application/pdf" });

      if (blob.size === 0) {
        throw new Error("Created blob is empty - base64 data may be invalid");
      }

      return blob;
    } catch (error) {
      throw new Error(`Failed to convert base64 to blob: ${error.message}`);
    }
  }

  async function handleSearch(event) {
    const userMessage = typeof event === 'string' ? event : event.detail;
    
    if (!userMessage || !userMessage.trim()) return;
    
    const trimmedMessage = userMessage.trim();
    
    // Add user message to chat immediately
    chatMessages = [...chatMessages, {
      type: 'user',
      content: trimmedMessage,
      timestamp: new Date()
    }];
    
    // Save to localStorage
    saveChatToStorage();
    
    loading = true;
    error = '';

    try {
      // Build conversation history from previous messages (for context-aware responses)
      // Include last 10 messages to maintain context without overwhelming the API
      const conversationHistory = chatMessages
        .slice(-10)  // Last 10 messages
        .filter(msg => {
          // Only include user and assistant messages (skip errors and special messages)
          const type = msg.type?.toLowerCase();
          return type === 'user' || type === 'assistant';
        })
        .map(msg => ({
          type: msg.type,
          content: msg.content || ''
        }));
      
      const requestHeaders = getAuthHeaders();

      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: requestHeaders,
        body: JSON.stringify({ 
          message: trimmedMessage,
          conversation_history: conversationHistory.length > 0 ? conversationHistory : undefined
        })
      }).catch(() => {
        throw new Error(`Cannot connect to backend at ${API_BASE_URL}. Make sure the backend server is running on port 8000.`);
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        const errorMsg = errData.detail || errData.message || `HTTP ${response.status}: ${response.statusText}`;
        throw new Error(errorMsg);
      }

      const data = await response.json();

      // Check if PDF was generated
      if (data.pdf_data && data.pdf_type) {
        
        // Decode base64 PDF and download it
        try {
          const pdfBlob = base64ToBlob(data.pdf_data, 'application/pdf');
          const url = URL.createObjectURL(pdfBlob);
          const link = document.createElement('a');
          link.href = url;
          
          // Generate filename based on PDF type
          const timestamp = new Date().toISOString().split('T')[0];
          if (data.pdf_type === 'resume') {
            link.download = `resume-${timestamp}.pdf`;
          } else if (data.pdf_type === 'person_profile') {
            // Try to extract person name from message for filename
            const personMatch = trimmedMessage.match(/(?:pdf of|generate pdf|create pdf|make pdf)\s+(.+?)(?:\.|$|and|with)/i);
            const personName = personMatch ? personMatch[1].trim().replace(/\s+/g, '-') : 'person';
            link.download = `${personName}-profile-${timestamp}.pdf`;
          } else {
            link.download = `document-${timestamp}.pdf`;
          }
          
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(url);
        } catch (pdfError) {
          // PDF download failed silently
        }
      }

      // Add AI response to chat
      const assistantMessage = {
        type: 'assistant',
        content: data.message || 'No response',
        timestamp: new Date(),
        person: data.person_data || null,
        pdfGenerated: !!data.pdf_data,
        pdfType: data.pdf_type
      };
      
      chatMessages = [...chatMessages, assistantMessage];
      
      // Save to localStorage
      saveChatToStorage();
      
      // Save this search to history (each search is a separate history item)
      saveSearchToHistory(trimmedMessage, assistantMessage);
      
      // Restore scroll position or scroll to bottom after new message
      setTimeout(() => {
        const chatContainer = document.querySelector('.chat-messages');
        if (chatContainer) {
          const savedScrollPosition = localStorage.getItem('chatScrollPosition');
          if (savedScrollPosition !== null) {
            // Restore saved scroll position
            chatContainer.scrollTop = parseInt(savedScrollPosition, 10);
            // Clear saved position after restoring
            localStorage.removeItem('chatScrollPosition');
          } else {
            // No saved position, scroll to bottom for new messages
            chatContainer.scrollTop = chatContainer.scrollHeight;
          }
        }
      }, 100);
      
    } catch (err) {
      const errorMessage = err.message || "Failed to fetch data. Check backend connection.";
      error = errorMessage;
      
      // Add error message to chat
      chatMessages = [...chatMessages, {
        type: 'error',
        content: errorMessage,
        timestamp: new Date()
      }];
      
      // Save to localStorage
      saveChatToStorage();
    } finally {
      loading = false;
    }
  }

  /**
   * Load search history from backend
   * Only shows history if chat is currently empty
   */
  async function loadHistory() {
    try {
      const response = await fetch(`${API_BASE_URL}/history`, {
        headers: getAuthHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        const historyMessages = (data.history || []).slice(0, 10).map(item => ({
          type: 'assistant',
          content: `Loaded profile for ${item.name} from cache.`,
          person: {
            name: item.name,
            bio: item.bio,
            news: item.news || [],
            images: item.images || [],
            source: 'cache'
          },
          timestamp: new Date(item.created_at)
        }));
        // Only show history if chat is empty
        if (chatMessages.length === 0 && historyMessages.length > 0) {
          chatMessages = historyMessages;
        }
      }
    } catch (err) {
      // history unavailable
    }
  }

  // ============================================
  // Chat Management
  // ============================================
  /**
   * Clear all chat messages
   */
  function clearChat() {
    if (confirm('Are you sure you want to clear all chat messages?')) {
      chatMessages = [];
      error = '';
      localStorage.removeItem('chatMessages');
      menuOpen = false; // Close menu after clearing
    }
  }

  /**
   * Start a new chat session
   */
  function newChat() {
    chatMessages = [];
    error = '';
    currentSessionId = getTodaySessionId();
    localStorage.setItem('chatMessages', JSON.stringify([]));
    menuOpen = false;
  }

  /**
   * Save/update the current session in history after each message exchange
   */
  function saveSearchToHistory(userMessage, assistantMessage) {
    try {
      if (!userMessage || !userMessage.trim()) return;

      const allHistory = JSON.parse(localStorage.getItem('chatHistory') || '[]');

      // Find existing session entry
      const existingIdx = allHistory.findIndex(s => s.id === currentSessionId);

      // Build full messages snapshot from chatMessages
      const messages = chatMessages.map(m => ({
        type: m.type,
        content: m.content,
        timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : m.timestamp,
        person: m.person || null,
        pdfGenerated: m.pdfGenerated || false,
        pdfType: m.pdfType || null,
      }));

      // Title = first user message of session
      const firstUser = messages.find(m => m.type === 'user');
      const title = firstUser ? firstUser.content.substring(0, 60) : userMessage.trim().substring(0, 60);

      if (existingIdx >= 0) {
        // Update existing session
        allHistory[existingIdx].messages = messages;
        allHistory[existingIdx].updatedAt = new Date().toISOString();
      } else {
        // Create new session entry at the top
        allHistory.unshift({
          id: currentSessionId,
          title,
          messages,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        });
      }

      localStorage.setItem('chatHistory', JSON.stringify(allHistory));
      chatHistory = allHistory;
    } catch (err) {
      // session save failed silently
    }
  }

  function saveChatToHistory() {} // kept for compatibility

  /**
   * Load chat history from localStorage
   */
  function loadChatHistory() {
    try {
      const saved = localStorage.getItem('chatHistory');
      if (saved) {
        chatHistory = JSON.parse(saved);
      }
    } catch (err) {
      // history load failed silently
    }
  }

  // Group history sessions by date label (Today, Yesterday, or date string)
  function getGroupedHistory(history) {
    const groups = {};
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterday = today - 86400000;

    for (const item of history) {
      try {
        const raw = item.updatedAt || item.createdAt;
        const d = raw ? new Date(raw) : new Date();
        if (isNaN(d.getTime())) throw new Error('invalid date');
        const dayStart = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
        let label;
        if (dayStart === today) label = 'Today';
        else if (dayStart === yesterday) label = 'Yesterday';
        else label = d.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
        if (!groups[label]) groups[label] = [];
        groups[label].push(item);
      } catch {
        if (!groups['Older']) groups['Older'] = [];
        groups['Older'].push(item);
      }
    }
    return Object.entries(groups).map(([label, items]) => ({ label, items }));
  }

  /**
   * Show/hide chat history panel
   */
  function toggleHistory() {
    if (!showHistory) {
      loadChatHistory();
    }
    showHistory = !showHistory;
    menuOpen = false; // Close menu after opening history
  }

  /**
   * Load a chat from history
   */
  function loadChatFromHistory(historyItem) {
    const msgs = historyItem.messages || [];
    chatMessages = msgs.map(msg => ({
      ...msg,
      timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
      person: msg.person || null,
      pdfGenerated: msg.pdfGenerated || false,
      pdfType: msg.pdfType || null
    }));
    hasStartedChatting = true;
    saveChatToStorage();
    showHistory = false;
    
    // Restore scroll position after loading
    setTimeout(() => {
      const chatContainer = document.querySelector('.chat-messages');
      if (chatContainer) {
        const savedScrollPosition = localStorage.getItem('chatScrollPosition');
        if (savedScrollPosition !== null) {
          chatContainer.scrollTop = parseInt(savedScrollPosition, 10);
          localStorage.removeItem('chatScrollPosition');
        } else {
          chatContainer.scrollTop = chatContainer.scrollHeight;
        }
      }
    }, 200);
  }

  /**
   * Delete a chat from history
   */
  function deleteChatFromHistory(id, event) {
    event.stopPropagation(); // Prevent loading the chat
    if (confirm('Delete this chat from history?')) {
      chatHistory = chatHistory.filter(chat => chat.id !== id);
      localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
    }
  }

  /**
   * Toggle three-dot menu
   */
  function toggleMenu() {
    menuOpen = !menuOpen;
  }

  /**
   * Close menu when clicking outside
   */
  function closeMenu() {
    menuOpen = false;
  }

  /**
   * Export chat conversation to PDF file
   * Uses jsPDF library to generate PDF client-side
   */
  async function exportToPDF() {
    if (chatMessages.length === 0) {
      alert('No chat messages to export');
      return;
    }
    menuOpen = false; // Close menu after exporting

    try {
      // Import jsPDF library dynamically
      const { jsPDF } = await import('jspdf');
      const doc = new jsPDF();
      
      // PDF layout constants
      let y = 20;  // Current vertical position
      const pageHeight = doc.internal.pageSize.height;
      const margin = 20;
      const lineHeight = 7;
      
      // Add PDF header
      doc.setFontSize(18);
      doc.text('Synapse - Conversation Export', margin, y);
      y += 15;
      
      doc.setFontSize(12);
      doc.text(`Exported on: ${new Date().toLocaleString()}`, margin, y);
      y += 10;
      
      // Add separator line
      doc.line(margin, y, doc.internal.pageSize.width - margin, y);
      y += 10;
      
      // Export chat messages
      doc.setFontSize(11);
      // Loop through each message and add to PDF
      for (const msg of chatMessages) {
        // Add new page if needed
        if (y > pageHeight - 30) {
          doc.addPage();
          y = 20;
        }
        
        // Handle user messages
        if (msg.type === 'user') {
          doc.setFont('helvetica', 'bold');
          doc.text('You:', margin, y);
          doc.setFont('helvetica', 'normal');
          const userText = doc.splitTextToSize(msg.content || '', doc.internal.pageSize.width - 2 * margin - 20);
          doc.text(userText, margin + 20, y);
          y += userText.length * lineHeight + 5;
        // Handle AI assistant messages with person data
        } else if (msg.type === 'assistant' && msg.person) {
          const person = msg.person;
          doc.setFont('helvetica', 'bold');
          doc.text('AI:', margin, y);
          doc.setFont('helvetica', 'normal');
          y += lineHeight;
          
          doc.setFont('helvetica', 'bold');
          doc.text(`Information about ${person.name}:`, margin + 10, y);
          y += lineHeight;
          
          if (person.bio) {
            doc.setFont('helvetica', 'bold');
            doc.text('Biography:', margin + 10, y);
            y += lineHeight;
            doc.setFont('helvetica', 'normal');
            const bioText = doc.splitTextToSize(person.bio, doc.internal.pageSize.width - 2 * margin - 20);
            doc.text(bioText, margin + 20, y);
            y += bioText.length * lineHeight + 5;
          }
          
          if (person.news && person.news.length > 0) {
            doc.setFont('helvetica', 'bold');
            doc.text('News:', margin + 10, y);
            y += lineHeight;
            doc.setFont('helvetica', 'normal');
            for (const newsItem of person.news) {
              if (y > pageHeight - 30) {
                doc.addPage();
                y = 20;
              }
              doc.text(`• ${newsItem.title}`, margin + 20, y);
              y += lineHeight;
            }
            y += 5;
          }
          
          if (person.images && person.images.length > 0) {
            doc.setFont('helvetica', 'bold');
            doc.text(`Images (${person.images.length}):`, margin + 10, y);
            y += lineHeight;
            doc.setFont('helvetica', 'normal');
            person.images.forEach((img, idx) => {
              if (y > pageHeight - 30) {
                doc.addPage();
                y = 20;
              }
              doc.text(`  [Image ${idx + 1}]`, margin + 20, y);
              y += lineHeight;
            });
          }
          
          y += 10;
        // Handle error messages
        } else if (msg.type === 'error') {
          doc.setFont('helvetica', 'italic');
          doc.setTextColor(200, 0, 0);
          doc.text(`Error: ${msg.content}`, margin, y);
          doc.setTextColor(0, 0, 0);
          y += lineHeight + 5;
        }
      }
      
      // Generate filename and save PDF
      const filename = `chat-export-${new Date().toISOString().split('T')[0]}.pdf`;
      doc.save(filename);
    } catch (err) {
      alert('Failed to export PDF. Please try again.');
    }
  }
  // emailTargetContent holds the text of the specific message to send
  let emailTargetContent = '';

  function copyMessage(content) {
    navigator.clipboard.writeText(content || '');
  }

  function openEmailModal(message) {
    emailAddress = '';
    emailStatus = '';
    emailStatusMessage = '';
    emailTargetContent = message.content || '';
    emailTargetPersonName = (message.person && message.person.name) ? message.person.name : '';
    emailSendType = emailTargetPersonName ? 'pdf' : 'text';
    showEmailModal = true;
  }

  async function sendEmail() {
    if (!emailAddress.trim()) return;
    emailSending = true;
    emailStatus = '';
    emailStatusMessage = '';

    try {
      if (emailSendType === 'pdf' && emailTargetPersonName) {
        const response = await fetch(`${API_BASE_URL}/email-pdf`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ email: emailAddress.trim(), person_name: emailTargetPersonName })
        });
        const data = await response.json();
        if (response.ok && data.success) {
          emailStatus = 'success';
          emailStatusMessage = `PDF report sent to ${emailAddress}!`;
        } else {
          emailStatus = 'error';
          emailStatusMessage = data.detail || data.error || 'Failed to send email.';
        }
      } else {
        const response = await fetch(`${API_BASE_URL}/email-text`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({
            email: emailAddress.trim(),
            subject: 'Response from Synapse',
            body: emailTargetContent,
          })
        });
        const data = await response.json();
        if (response.ok && data.success) {
          emailStatus = 'success';
          emailStatusMessage = `Sent to ${emailAddress}!`;
        } else {
          emailStatus = 'error';
          emailStatusMessage = data.detail || data.error || 'Failed to send email.';
        }
      }
    } catch (err) {
      emailStatus = 'error';
      emailStatusMessage = err.message || 'Failed to send email.';
    } finally {
      emailSending = false;
    }
  }

  async function generatePersonPDF(name) {
    try {
      // Show loading state
      loading = true;

      const response = await fetch(`${API_BASE_URL}/person/pdf`, {
        method: "POST",
        headers: {
          ...getAuthHeaders(),
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ person_name: name })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: response.statusText }));
        throw new Error(errorData.message || `Backend returned error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();

      if (!data.pdf_data) {
        throw new Error(data.message || "Backend did not return PDF data");
      }

      // Decode base64 PDF and download it
      const pdfBlob = base64ToBlob(data.pdf_data, "application/pdf");

      if (!pdfBlob || pdfBlob.size === 0) {
        throw new Error("Failed to create PDF blob - blob is empty");
      }
      
      const filename = `${name.replace(/\s+/g, "_")}-profile.pdf`;
      
      // Use data URL directly (never gets revoked, most reliable)
      const dataUrl = `data:application/pdf;base64,${data.pdf_data}`;
      
      // Create download link with data URL
      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = filename;
      link.style.display = "none";
      link.setAttribute("download", filename);
      
      // Append to body
      document.body.appendChild(link);
      
      // Force reflow
      link.offsetHeight;
      
      // Trigger download IMMEDIATELY (must be in user interaction context)
      link.click();
      
      // Show notification
      const notification = document.createElement('div');
      notification.textContent = `📥 Downloading ${filename}...`;
      notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #10b981;
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        font-size: 14px;
        font-weight: 500;
      `;
      document.body.appendChild(notification);
      
      // Show success message with download button (using data URL)
      chatMessages = [...chatMessages, {
        type: 'assistant',
        content: `📥 PDF download started! Check your browser's download folder for "${filename}"\n\nIf it doesn't appear, click the download button below.`,
        timestamp: new Date(),
        pdfDownloadUrl: dataUrl,
        pdfFilename: filename
      }];
      saveChatToStorage();
      
      // Clean up after delay
      setTimeout(() => {
        if (link.parentNode) {
          document.body.removeChild(link);
        }
        if (notification.parentNode) {
          notification.style.opacity = '0';
          notification.style.transition = 'opacity 0.3s';
          setTimeout(() => {
            if (notification.parentNode) {
              notification.parentNode.removeChild(notification);
            }
          }, 300);
        }
      }, 2000);

      // Show success message
      chatMessages = [...chatMessages, {
        type: 'assistant',
        content: `✅ PDF generated successfully for ${name}!`,
        timestamp: new Date()
      }];
      saveChatToStorage();
      
    } catch (err) {
      const errorMessage = err.message || "Failed to generate PDF. Please try again.";
      
      // Show error message to user
      chatMessages = [...chatMessages, {
        type: 'error',
        content: `❌ PDF Generation Failed: ${errorMessage}`,
        timestamp: new Date()
      }];
      saveChatToStorage();
    } finally {
      loading = false;
    }
  }

</script>

<!-- Background image is set in global.css -->
<!-- Solar System Planets -->
<div class="planet-saturn"></div>
<div class="planet-earth"></div>
<div class="planet-mars"></div>
<div class="planet-venus"></div>
<div class="planet-mercury"></div>
<div class="planet-neptune"></div>

<main>
  {#if hasStartedChatting}
    <!-- Three-dot menu button (only visible on chat page) -->
    <button class="menu-toggle" on:click={toggleMenu} aria-label="Menu" title="Menu">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <circle cx="12" cy="6" r="1.5" fill="currentColor"/>
        <circle cx="12" cy="12" r="1.5" fill="currentColor"/>
        <circle cx="12" cy="18" r="1.5" fill="currentColor"/>
      </svg>
    </button>

    <!-- Menu dropdown -->
    {#if menuOpen}
    <div class="menu-overlay" on:click={closeMenu} role="button" tabindex="0" on:keydown={(e) => e.key === 'Escape' && closeMenu()}></div>
    <div class="menu-dropdown">
      <button class="menu-item menu-item-new-chat" on:click={newChat}>
        <div class="menu-item-content">
          <div class="menu-icon-wrapper">
            <span class="menu-icon">💬</span>
            <span class="menu-icon-glow"></span>
          </div>
          <span class="menu-item-text">New Chat</span>
        </div>
        <span class="menu-item-arrow">→</span>
      </button>
      <button class="menu-item menu-item-history" on:click={toggleHistory}>
        <div class="menu-item-content">
          <div class="menu-icon-wrapper">
            <span class="menu-icon">📚</span>
            <span class="menu-icon-glow"></span>
          </div>
          <span class="menu-item-text">Search History</span>
        </div>
        <span class="menu-item-arrow">→</span>
      </button>
      <div class="menu-divider"></div>
      <!-- LLM Provider Selector -->
      <div class="menu-item-llm">
        <div class="llm-selector-header">
          <div class="llm-icon-wrapper">
            <span class="llm-icon">🤖</span>
            <span class="llm-icon-glow"></span>
          </div>
          <label for="llm-provider-select" class="menu-llm-label">AI Model</label>
        </div>
        <div class="llm-select-wrapper">
          <select 
            id="llm-provider-select"
            class="menu-llm-select"
            value={currentProvider}
            on:change={(e) => {
              const newProvider = e.target.value;
              if (newProvider !== currentProvider) {
                switchProvider(newProvider);
              }
            }}
            disabled={providerLoading}
            title="Select LLM Provider"
          >
            {#each availableProviders as provider}
              <option value={provider}>
                {provider === 'openai' ? '✨ OpenAI' : '🌟 Gemini'}
              </option>
            {/each}
          </select>
          <div class="llm-select-arrow">▼</div>
          {#if providerLoading}
            <div class="llm-loading-spinner"></div>
          {/if}
        </div>
        <div class="llm-provider-badge" class:active-openai={currentProvider === 'openai'} class:active-gemini={currentProvider === 'gemini'}>
          <span class="badge-dot"></span>
          <span class="badge-text">{currentProvider === 'openai' ? 'OpenAI Active' : 'Gemini Active'}</span>
        </div>
      </div>
      <div class="menu-divider"></div>
      <button class="menu-item menu-item-export" on:click={exportToPDF} disabled={chatMessages.length === 0}>
        <div class="menu-item-content">
          <div class="menu-icon-wrapper">
            <span class="menu-icon">📄</span>
            <span class="menu-icon-glow"></span>
          </div>
          <span class="menu-item-text">Export PDF</span>
        </div>
        <span class="menu-item-arrow">→</span>
      </button>
      <button class="menu-item menu-item-clear" on:click={clearChat} disabled={chatMessages.length === 0}>
        <div class="menu-item-content">
          <div class="menu-icon-wrapper">
            <span class="menu-icon">🗑️</span>
            <span class="menu-icon-glow"></span>
          </div>
          <span class="menu-item-text">Clear Chat</span>
        </div>
        <span class="menu-item-arrow">→</span>
      </button>
    </div>
    {/if}
  {/if}

  <!-- Chat History Panel -->
  {#if showHistory}
    <div class="history-overlay" on:click={toggleHistory} role="button" tabindex="0" on:keydown={(e) => e.key === 'Escape' && toggleHistory()}></div>
    <div class="history-panel">
      <div class="history-header">
        <h2>Search History</h2>
        <button class="history-close" on:click={toggleHistory} aria-label="Close">×</button>
      </div>
      <div class="history-list">
        {#if chatHistory.length === 0}
          <div class="history-empty">
            <p>No search history yet</p>
            <p class="history-empty-sub">Your searches will appear here</p>
          </div>
        {:else}
          {#each getGroupedHistory(chatHistory) as group}
            <div class="history-date-label">{group.label}</div>
            {#each group.items as item}
              <div class="history-item" on:click={() => loadChatFromHistory(item)} role="button" tabindex="0" on:keydown={(e) => e.key === 'Enter' && loadChatFromHistory(item)}>
                <div class="history-item-content">
                  <div class="history-item-title">
                    {item.title || (item.personName ? `👤 ${item.personName}` : `🔍 ${item.searchQuery || 'Chat'}`)}
                  </div>
                  <div class="history-item-meta">
                    {new Date(item.updatedAt || item.createdAt).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                    · {(item.messages || []).filter(m => m.type === 'user').length || 1} msg
                  </div>
                </div>
                <button
                  class="history-item-delete"
                  on:click={(e) => deleteChatFromHistory(item.id, e)}
                  aria-label="Delete"
                >
                  🗑️
                </button>
              </div>
            {/each}
          {/each}
        {/if}
      </div>
    </div>
  {/if}

  <!-- Email Modal -->
  {#if showEmailModal}
    <div class="modal-overlay" on:click={() => showEmailModal = false} role="button" tabindex="0" on:keydown={(e) => e.key === 'Escape' && (showEmailModal = false)}></div>
    <div class="email-modal">
      <div class="email-modal-header">
        <h3>📧 Send via Email</h3>
        <button class="modal-close" on:click={() => showEmailModal = false}>×</button>
      </div>

      <div class="email-modal-body">
        <label class="email-label">Recipient Email</label>
        <input
          class="email-input"
          type="email"
          placeholder="receiver@example.com"
          bind:value={emailAddress}
          disabled={emailSending}
        />

        {#if emailTargetPersonName}
          <label class="email-label" style="margin-top: 1rem;">Send as</label>
          <div class="email-type-options">
            <label class="email-type-option">
              <input type="radio" bind:group={emailSendType} value="text" disabled={emailSending} />
              <span>Text answer</span>
            </label>
            <label class="email-type-option">
              <input type="radio" bind:group={emailSendType} value="pdf" disabled={emailSending} />
              <span>PDF Report ({emailTargetPersonName})</span>
            </label>
          </div>
        {/if}

        {#if emailStatus === 'success'}
          <div class="email-status success">{emailStatusMessage}</div>
        {:else if emailStatus === 'error'}
          <div class="email-status error">{emailStatusMessage}</div>
        {/if}
      </div>

      <div class="email-modal-footer">
        <button class="email-cancel-btn" on:click={() => showEmailModal = false} disabled={emailSending}>Cancel</button>
        <button class="email-send-btn" on:click={sendEmail} disabled={emailSending || !emailAddress.trim()}>
          {emailSending ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  {/if}

  {#if !hasStartedChatting}
    <!-- Landing Page -->
    <div class="landing-page">
      <div class="landing-content">
        <h1 class="landing-title">
          <span class="title-syn">Syn</span><span class="title-apse">apse</span>
        </h1>
        <p class="landing-subtitle">Where curiosity meets intelligence</p>
        <button class="start-chatting-btn" on:click={startChatting}>
          <span class="comet-trail"></span>
          <span class="btn-text">Start Chatting</span>
          <span class="comet-icon">☄️</span>
        </button>
      </div>
    </div>
  {:else}
    <!-- Chat Interface -->
    <!-- Back to Main Page Button -->
    <button class="back-to-main-btn" on:click={goBackToMain} title="Back to Main Page">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M19 12H5M12 19l-7-7 7-7"/>
      </svg>
    </button>

    <div class="container">
      <div class="chat-container">
        <div class="chat-messages">
          {#each chatMessages as message}
            {#if message.type === 'user'}
              <div class="message user-message">
                <div class="message-content">
                  <strong>You:</strong> {message.content}
                </div>
                <div class="message-time">{message.timestamp.toLocaleTimeString()}</div>
              </div>
            {:else if message.type === 'error'}
              <div class="message error-message">
                <div class="message-content">
                  <span class="error-icon">⚠️</span> 
                  {message.content}
                  {#if message.downloadLink}
                    <a href={message.downloadLink} download={message.downloadFilename} class="download-link-btn">
                      📥 Download PDF
                    </a>
                  {/if}
                </div>
              </div>
              {:else if message.type === 'assistant'}
              <div class="message assistant-message msg-hoverable">
                <div class="message-content">
                  <strong>AI:</strong>

                  <!-- AI text response -->
                  <div class="ai-response-text">
                    {message.content || 'No response'}
                  </div>

                  <!-- PDF Download Button -->
                  {#if message.pdfDownloadUrl}
                    <a href={message.pdfDownloadUrl} download={message.pdfFilename} class="pdf-download-btn">
                      📥 Download PDF ({message.pdfFilename})
                    </a>
                  {/if}

                  <!-- ⭐ If backend returned structured person data, show PersonCard -->
                  {#if message.person && message.person.name}
                    <PersonCard person={message.person} generatePDF={generatePersonPDF} />
                  {/if}

                </div>

                <div class="message-footer">
                  <div class="message-time">{message.timestamp.toLocaleTimeString()}</div>
                  <div class="msg-toolbar">
                    <button class="msg-tool-btn" on:click={() => copyMessage(message.content)} title="Copy">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                    </button>
                    {#if message.person && message.person.name}
                    <button class="msg-tool-btn" on:click={() => openEmailModal(message)} title="Send via email">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                    </button>
                    {/if}
                  </div>
                </div>
              </div>
            
            {/if}
          {/each}

          {#if loading}
            <div class="message assistant-message">
              <div class="message-content loading">
                <span class="spinner"></span>
                Thinking...
              </div>
            </div>
          {/if}
        </div>
      </div>
      
      <!-- Search Bar Footer -->
      <footer class="search-footer">
        <SearchBox on:search={handleSearch} {loading} />
      </footer>
    </div>
  {/if}
</main>

<style>
  /* Global Typography */
  * {
    font-family: 'Poppins', 'Space Grotesk', 'Inter', sans-serif;
  }

  main {
    min-height: 100vh;
    padding: 2rem 0;
    display: flex;
    flex-direction: column;
    position: relative;
    z-index: 1;
  }

  .container {
    max-width: 900px;
    margin: 0 auto;
    padding: 0 1rem;
    display: flex;
    flex-direction: column;
    height: 100%;
    position: relative;
    z-index: 1;
  }

  .header {
    text-align: center;
    margin-bottom: 2rem;
    animation: fadeInDown 0.6s ease-out;
    position: relative;
  }

  .title {
    font-family: 'Poppins', 'Outfit', sans-serif;
    font-size: 3rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    background: linear-gradient(135deg, #ffffff 0%, #a0a0ff 30%, #8b5cf6 60%, #ff6b9d 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.5rem;
    text-shadow: 0 0 40px rgba(139, 92, 246, 0.5), 0 0 80px rgba(139, 92, 246, 0.3);
    filter: drop-shadow(0 4px 20px rgba(139, 92, 246, 0.4));
    animation: gradientShift 3s ease infinite;
    background-size: 200% 200%;
  }

  @keyframes gradientShift {
    0%, 100% {
      background-position: 0% 50%;
    }
    50% {
      background-position: 100% 50%;
    }
  }

  .title-icon {
    display: inline-block;
    margin-right: 1rem;
    font-size: 3rem;
  }

  .subtitle {
    font-family: 'Space Grotesk', 'Inter', sans-serif;
    font-size: 1.1rem;
    color: rgba(255, 255, 255, 0.85);
    font-weight: 400;
    letter-spacing: 1px;
    margin-bottom: 0.5rem;
    text-transform: uppercase;
    text-shadow: 0 2px 15px rgba(139, 92, 246, 0.4), 0 0 30px rgba(139, 92, 246, 0.2);
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(200, 200, 255, 0.7) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  /* Three-dot menu styles */
  .menu-toggle {
    position: fixed !important;
    top: 1.5rem !important;
    right: 1.5rem !important;
    left: auto !important;
    background: rgba(99, 102, 241, 1) !important;
    border: 3px solid rgba(255, 255, 255, 0.9) !important;
    color: white !important;
    width: 56px !important;
    height: 56px !important;
    border-radius: 14px !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    z-index: 1002 !important;
    transition: all 0.3s ease;
    backdrop-filter: blur(10px);
    box-shadow: 0 6px 30px rgba(99, 102, 241, 1), 0 0 50px rgba(99, 102, 241, 0.8), inset 0 0 20px rgba(255, 255, 255, 0.2);
  }

  .menu-toggle:hover {
    background: rgba(99, 102, 241, 1);
    border-color: rgba(139, 92, 246, 1);
    transform: scale(1.1);
    box-shadow: 0 6px 30px rgba(99, 102, 241, 0.8), 0 0 40px rgba(99, 102, 241, 0.6);
  }

  .menu-toggle svg {
    stroke: white;
    stroke-width: 2.5;
  }

  .menu-overlay {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 100% !important;
    height: 100% !important;
    background: rgba(0, 0, 0, 0.4) !important;
    z-index: 1000 !important;
    backdrop-filter: blur(2px);
  }

  .menu-dropdown {
    position: fixed !important;
    top: 5rem !important;
    right: 1.5rem !important;
    left: auto !important;
    background: rgba(30, 30, 40, 0.98) !important;
    border: 2px solid rgba(139, 92, 246, 0.5) !important;
    border-radius: 10px !important;
    padding: 0.4rem !important;
    min-width: 180px !important;
    max-width: 250px !important;
    z-index: 1001 !important;
    backdrop-filter: blur(20px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.8), 0 0 40px rgba(99, 102, 241, 0.4) !important;
    animation: slideDown 0.2s ease-out;
    transform-origin: top right;
  }

  @keyframes slideDown {
    from {
      opacity: 0;
      transform: translateY(-10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .menu-item {
    width: 100%;
    background: linear-gradient(135deg, rgba(30, 30, 40, 0.6) 0%, rgba(40, 40, 55, 0.6) 100%);
    border: 1.5px solid rgba(139, 92, 246, 0.2);
    border-radius: 8px;
    color: white;
    padding: 0.55rem 0.75rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    font-size: 0.85rem;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    text-align: left;
    position: relative;
    overflow: hidden;
    margin-bottom: 0.35rem;
  }

  .menu-item::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
    transition: left 0.5s ease;
  }

  .menu-item:hover:not(:disabled)::before {
    left: 100%;
  }

  .menu-item:hover:not(:disabled) {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.25) 0%, rgba(99, 102, 241, 0.2) 100%);
    border-color: rgba(139, 92, 246, 0.6);
    box-shadow: 0 3px 15px rgba(139, 92, 246, 0.3), inset 0 0 15px rgba(139, 92, 246, 0.1);
    transform: translateX(3px) translateY(-1px);
  }

  .menu-item:active:not(:disabled) {
    transform: translateX(3px) translateY(-1px) scale(0.98);
  }

  .menu-item:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    filter: grayscale(0.5);
  }

  .menu-item-content {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex: 1;
  }

  .menu-icon-wrapper {
    position: relative;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .menu-icon {
    font-size: 1.1rem;
    filter: drop-shadow(0 0 4px rgba(139, 92, 246, 0.6));
    transition: all 0.3s ease;
    position: relative;
    z-index: 1;
  }

  .menu-icon-glow {
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.3) 0%, transparent 70%);
    opacity: 0;
    transition: opacity 0.3s ease;
  }

  .menu-item:hover:not(:disabled) .menu-icon {
    transform: scale(1.1) rotate(5deg);
    filter: drop-shadow(0 0 8px rgba(139, 92, 246, 0.9));
  }

  .menu-item:hover:not(:disabled) .menu-icon-glow {
    opacity: 1;
    animation: iconGlowPulse 1.5s ease-in-out infinite;
  }

  @keyframes iconGlowPulse {
    0%, 100% {
      transform: scale(1);
      opacity: 0.6;
    }
    50% {
      transform: scale(1.3);
      opacity: 0.9;
    }
  }

  .menu-item-text {
    font-family: 'Space Grotesk', 'Poppins', sans-serif;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-size: 0.8rem;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(200, 200, 255, 0.9) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: 0 2px 8px rgba(139, 92, 246, 0.4), 0 0 20px rgba(139, 92, 246, 0.2);
    transition: all 0.3s ease;
    position: relative;
  }

  .menu-item:hover:not(:disabled) .menu-item-text {
    background: linear-gradient(135deg, rgba(255, 255, 255, 1) 0%, rgba(180, 180, 255, 1) 50%, rgba(255, 255, 255, 1) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: 0 2px 12px rgba(139, 92, 246, 0.6), 0 0 30px rgba(139, 92, 246, 0.4);
    letter-spacing: 0.7px;
    transform: scale(1.02);
  }

  .menu-item-arrow {
    opacity: 0;
    transform: translateX(-8px);
    transition: all 0.3s ease;
    color: rgba(139, 92, 246, 0.8);
    font-size: 1rem;
    font-weight: bold;
  }

  .menu-item:hover:not(:disabled) .menu-item-arrow {
    opacity: 1;
    transform: translateX(0);
  }

  /* Specific styles for each menu item */
  .menu-item-new-chat {
    border-color: rgba(59, 130, 246, 0.3);
  }

  .menu-item-new-chat:hover:not(:disabled) {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.25) 0%, rgba(37, 99, 235, 0.2) 100%);
    border-color: rgba(59, 130, 246, 0.6);
    box-shadow: 0 3px 15px rgba(59, 130, 246, 0.3), inset 0 0 15px rgba(59, 130, 246, 0.1);
  }

  .menu-item-new-chat .menu-icon {
    filter: drop-shadow(0 0 4px rgba(59, 130, 246, 0.6));
  }

  .menu-item-new-chat:hover:not(:disabled) .menu-icon {
    filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.9));
  }

  .menu-item-history {
    border-color: rgba(168, 85, 247, 0.3);
  }

  .menu-item-history:hover:not(:disabled) {
    background: linear-gradient(135deg, rgba(168, 85, 247, 0.25) 0%, rgba(147, 51, 234, 0.2) 100%);
    border-color: rgba(168, 85, 247, 0.6);
    box-shadow: 0 3px 15px rgba(168, 85, 247, 0.3), inset 0 0 15px rgba(168, 85, 247, 0.1);
  }

  .menu-item-history .menu-icon {
    filter: drop-shadow(0 0 4px rgba(168, 85, 247, 0.6));
  }

  .menu-item-history:hover:not(:disabled) .menu-icon {
    filter: drop-shadow(0 0 8px rgba(168, 85, 247, 0.9));
  }

  .menu-item-export {
    border-color: rgba(34, 197, 94, 0.3);
  }

  .menu-item-export:hover:not(:disabled) {
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.25) 0%, rgba(22, 163, 74, 0.2) 100%);
    border-color: rgba(34, 197, 94, 0.6);
    box-shadow: 0 3px 15px rgba(34, 197, 94, 0.3), inset 0 0 15px rgba(34, 197, 94, 0.1);
  }

  .menu-item-export .menu-icon {
    filter: drop-shadow(0 0 4px rgba(34, 197, 94, 0.6));
  }

  .menu-item-export:hover:not(:disabled) .menu-icon {
    filter: drop-shadow(0 0 8px rgba(34, 197, 94, 0.9));
  }

  .menu-item-clear {
    border-color: rgba(239, 68, 68, 0.3);
  }

  .menu-item-clear:hover:not(:disabled) {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.25) 0%, rgba(220, 38, 38, 0.2) 100%);
    border-color: rgba(239, 68, 68, 0.6);
    box-shadow: 0 3px 15px rgba(239, 68, 68, 0.3), inset 0 0 15px rgba(239, 68, 68, 0.1);
  }

  .menu-item-clear .menu-icon {
    filter: drop-shadow(0 0 4px rgba(239, 68, 68, 0.6));
  }

  .menu-item-clear:hover:not(:disabled) .menu-icon {
    filter: drop-shadow(0 0 8px rgba(239, 68, 68, 0.9));
  }

  .menu-divider {
    height: 1.5px;
    background: linear-gradient(90deg, transparent, rgba(139, 92, 246, 0.5), transparent);
    margin: 0.5rem 0;
    border-radius: 2px;
    box-shadow: 0 0 8px rgba(139, 92, 246, 0.3);
  }

  /* LLM Provider Selector in Menu */
  .menu-item-llm {
    padding: 0.7rem;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.1) 100%);
    border: 1.5px solid rgba(139, 92, 246, 0.3);
    border-radius: 10px;
    margin: 0.35rem 0;
    position: relative;
    overflow: hidden;
    transition: all 0.3s ease;
  }

  .menu-item-llm::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
    animation: shimmer 3s infinite;
  }

  @keyframes shimmer {
    0% { left: -100%; }
    100% { left: 100%; }
  }

  .menu-item-llm:hover {
    border-color: rgba(139, 92, 246, 0.6);
    box-shadow: 0 0 15px rgba(139, 92, 246, 0.4), inset 0 0 15px rgba(139, 92, 246, 0.1);
    transform: translateY(-1px);
  }

  .llm-selector-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.6rem;
  }

  .llm-icon-wrapper {
    position: relative;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .llm-icon {
    font-size: 1.2rem;
    filter: drop-shadow(0 0 6px rgba(99, 102, 241, 0.8));
    animation: iconPulse 2s ease-in-out infinite;
    position: relative;
    z-index: 1;
  }

  @keyframes iconPulse {
    0%, 100% {
      transform: scale(1);
      filter: drop-shadow(0 0 8px rgba(99, 102, 241, 0.8));
    }
    50% {
      transform: scale(1.1);
      filter: drop-shadow(0 0 15px rgba(139, 92, 246, 1));
    }
  }

  .llm-icon-glow {
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.4) 0%, transparent 70%);
    animation: glowPulse 2s ease-in-out infinite;
  }

  @keyframes glowPulse {
    0%, 100% {
      opacity: 0.5;
      transform: scale(1);
    }
    50% {
      opacity: 0.8;
      transform: scale(1.2);
    }
  }

  .menu-llm-label {
    font-family: 'Outfit', 'Space Grotesk', sans-serif;
    color: rgba(255, 255, 255, 0.95);
    font-size: 0.85rem;
    font-weight: 700;
    white-space: nowrap;
    text-transform: uppercase;
    letter-spacing: 1px;
    background: linear-gradient(135deg, rgba(255, 255, 255, 1) 0%, rgba(200, 180, 255, 0.9) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: 0 2px 10px rgba(139, 92, 246, 0.5), 0 0 25px rgba(139, 92, 246, 0.3);
    filter: drop-shadow(0 0 8px rgba(139, 92, 246, 0.4));
  }

  .llm-select-wrapper {
    position: relative;
    margin-bottom: 0.4rem;
  }

  .menu-llm-select {
    width: 100%;
    min-width: 120px;
    background: linear-gradient(135deg, rgba(30, 30, 40, 0.95) 0%, rgba(40, 40, 55, 0.95) 100%);
    border: 1.5px solid rgba(139, 92, 246, 0.5);
    border-radius: 8px;
    color: white;
    padding: 0.55rem 2rem 0.55rem 0.75rem;
    font-family: 'Space Grotesk', 'Poppins', sans-serif;
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.3px;
    cursor: pointer;
    transition: all 0.3s ease;
    appearance: none;
    -webkit-appearance: none;
    -moz-appearance: none;
    box-shadow: 0 3px 12px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1);
    text-shadow: 0 0 8px rgba(139, 92, 246, 0.3);
  }

  .menu-llm-select:hover:not(:disabled) {
    border-color: rgba(139, 92, 246, 0.8);
    background: linear-gradient(135deg, rgba(40, 40, 55, 1) 0%, rgba(50, 50, 70, 1) 100%);
    box-shadow: 0 6px 25px rgba(139, 92, 246, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.15);
    transform: translateY(-1px);
  }

  .menu-llm-select:focus {
    outline: none;
    border-color: rgba(139, 92, 246, 1);
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.3), 0 6px 25px rgba(139, 92, 246, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.15);
  }

  .menu-llm-select:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    filter: grayscale(0.3);
  }

  .menu-llm-select option {
    background: rgba(30, 30, 40, 1);
    color: white;
    padding: 0.5rem;
  }

  .llm-select-arrow {
    position: absolute;
    right: 0.75rem;
    top: 50%;
    transform: translateY(-50%);
    color: rgba(139, 92, 246, 0.8);
    font-size: 0.65rem;
    pointer-events: none;
    transition: all 0.3s ease;
  }

  .menu-llm-select:hover + .llm-select-arrow,
  .menu-llm-select:focus + .llm-select-arrow {
    color: rgba(139, 92, 246, 1);
    transform: translateY(-50%) scale(1.2);
  }

  .llm-loading-spinner {
    position: absolute;
    right: 2rem;
    top: 50%;
    transform: translateY(-50%);
    width: 14px;
    height: 14px;
    border: 2px solid rgba(139, 92, 246, 0.3);
    border-top-color: rgba(139, 92, 246, 1);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: translateY(-50%) rotate(360deg); }
  }

  .llm-provider-badge {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.3rem 0.6rem;
    background: rgba(30, 30, 40, 0.6);
    border-radius: 6px;
    border: 1px solid rgba(139, 92, 246, 0.2);
    transition: all 0.3s ease;
  }

  .llm-provider-badge.active-openai {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(5, 150, 105, 0.15) 100%);
    border-color: rgba(16, 185, 129, 0.4);
    box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
  }

  .llm-provider-badge.active-gemini {
    background: linear-gradient(135deg, rgba(251, 191, 36, 0.2) 0%, rgba(245, 158, 11, 0.15) 100%);
    border-color: rgba(251, 191, 36, 0.4);
    box-shadow: 0 0 10px rgba(251, 191, 36, 0.3);
  }

  .badge-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgba(139, 92, 246, 0.6);
    animation: dotPulse 2s ease-in-out infinite;
    transition: background 0.3s ease;
  }

  .llm-provider-badge.active-openai .badge-dot {
    background: rgba(16, 185, 129, 1);
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.8);
  }

  .llm-provider-badge.active-gemini .badge-dot {
    background: rgba(251, 191, 36, 1);
    box-shadow: 0 0 8px rgba(251, 191, 36, 0.8);
  }

  @keyframes dotPulse {
    0%, 100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.7;
      transform: scale(1.2);
    }
  }

  .badge-text {
    font-family: 'Outfit', 'Space Grotesk', sans-serif;
    color: rgba(255, 255, 255, 0.95);
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    text-shadow: 0 1px 6px rgba(139, 92, 246, 0.5), 0 0 15px rgba(139, 92, 246, 0.3);
  }

  /* Chat History Panel Styles */
  .history-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    z-index: 99997;
    backdrop-filter: blur(4px);
  }

  .history-panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 400px;
    max-width: 90vw;
    height: 100vh;
    background: rgba(20, 20, 30, 0.98);
    border-left: 2px solid rgba(139, 92, 246, 0.5);
    z-index: 99998;
    display: flex;
    flex-direction: column;
    box-shadow: -8px 0 32px rgba(0, 0, 0, 0.8);
    animation: slideInRight 0.3s ease-out;
  }

  @keyframes slideInRight {
    from {
      transform: translateX(100%);
    }
    to {
      transform: translateX(0);
    }
  }

  .history-header {
    padding: 1.5rem;
    border-bottom: 1px solid rgba(139, 92, 246, 0.3);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .history-header h2 {
    color: white;
    font-size: 1.5rem;
    margin: 0;
  }

  .history-close {
    background: transparent;
    border: none;
    color: white;
    font-size: 2rem;
    cursor: pointer;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    transition: all 0.2s ease;
  }

  .history-close:hover {
    background: rgba(139, 92, 246, 0.2);
  }

  .history-list {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
  }

  .history-empty {
    text-align: center;
    padding: 3rem 1rem;
    color: rgba(255, 255, 255, 0.6);
  }

  .history-empty-sub {
    font-size: 0.9rem;
    margin-top: 0.5rem;
    opacity: 0.5;
  }

  .history-date-label {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(139, 92, 246, 0.8);
    padding: 0.6rem 1rem 0.3rem;
    margin-top: 0.5rem;
  }

  .history-item {
    background: rgba(30, 30, 40, 0.8);
    border: 1px solid rgba(139, 92, 246, 0.2);
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .history-item:hover {
    background: rgba(139, 92, 246, 0.2);
    border-color: rgba(139, 92, 246, 0.5);
    transform: translateX(-4px);
  }

  .history-item-content {
    flex: 1;
    min-width: 0;
  }

  .history-item-title {
    color: white;
    font-weight: 500;
    margin-bottom: 0.25rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .history-item-meta {
    color: rgba(255, 255, 255, 0.5);
    font-size: 0.85rem;
  }

  .history-item-delete {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.6);
    cursor: pointer;
    padding: 0.5rem;
    border-radius: 6px;
    transition: all 0.2s ease;
    font-size: 1.2rem;
    flex-shrink: 0;
  }

  .history-item-delete:hover {
    background: rgba(239, 68, 68, 0.2);
    color: rgba(239, 68, 68, 1);
  }

  /* Landing Page Styles */
  .landing-page {
    min-height: 100vh;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 2rem;
    position: relative;
    z-index: 1;
    padding-top: 15vh; /* Much higher up on the page */
  }

  .landing-content {
    text-align: center;
    max-width: 800px;
    animation: fadeInUp 0.8s ease-out;
  }

  .landing-title {
    font-family: 'Poppins', 'Outfit', sans-serif;
    font-size: 5rem;
    font-weight: 900;
    letter-spacing: -3px;
    margin-bottom: 1rem;
    line-height: 1;
    filter: drop-shadow(0 4px 30px rgba(139, 92, 246, 0.6));
  }

  .title-syn {
    background: linear-gradient(135deg, #ffffff 0%, #c4b5fd 60%, #8b5cf6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .title-apse {
    background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 60%, #ff6b9d 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: glow 2s ease-in-out infinite alternate;
  }

  .landing-subtitle {
    font-family: 'Space Grotesk', 'Outfit', sans-serif;
    font-size: 1.15rem;
    font-weight: 500;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 3rem;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(200, 180, 255, 0.85) 50%, rgba(255, 255, 255, 0.95) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: 0 2px 20px rgba(139, 92, 246, 0.5), 0 0 40px rgba(139, 92, 246, 0.3);
    filter: drop-shadow(0 2px 15px rgba(139, 92, 246, 0.4));
  }

  .start-chatting-btn {
    position: relative;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #ec4899 100%);
    border: 3px solid rgba(255, 255, 255, 0.3);
    color: white;
    font-family: 'Outfit', 'Space Grotesk', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    padding: 1.2rem 2.5rem;
    border-radius: 50px;
    cursor: pointer;
    overflow: hidden;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 
      0 10px 40px rgba(99, 102, 241, 0.5),
      0 0 60px rgba(139, 92, 246, 0.4),
      inset 0 0 30px rgba(255, 255, 255, 0.1);
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 3px;
    text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3), 0 0 20px rgba(255, 255, 255, 0.2);
  }

  .start-chatting-btn:hover {
    transform: translateY(-5px) scale(1.05);
    box-shadow: 
      0 15px 50px rgba(99, 102, 241, 0.7),
      0 0 80px rgba(139, 92, 246, 0.6),
      inset 0 0 40px rgba(255, 255, 255, 0.2);
    border-color: rgba(255, 255, 255, 0.6);
  }

  .start-chatting-btn:active {
    transform: translateY(-2px) scale(1.02);
  }

  .comet-trail {
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.4),
      transparent
    );
    animation: cometSweep 2s ease-in-out infinite;
  }

  @keyframes cometSweep {
    0% {
      left: -100%;
    }
    100% {
      left: 100%;
    }
  }

  .btn-text {
    position: relative;
    z-index: 1;
    font-family: 'Outfit', 'Space Grotesk', sans-serif;
    font-weight: 700;
    letter-spacing: 2px;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }

  .comet-icon {
    position: relative;
    z-index: 1;
    font-size: 1.5rem;
    animation: cometFloat 2s ease-in-out infinite;
    filter: drop-shadow(0 0 10px rgba(255, 255, 255, 0.8));
  }

  @keyframes cometFloat {
    0%, 100% {
      transform: translateX(0) rotate(0deg);
    }
    50% {
      transform: translateX(10px) rotate(180deg);
    }
  }

  @keyframes glow {
    0% {
      filter: drop-shadow(0 0 20px rgba(99, 102, 241, 0.5));
    }
    100% {
      filter: drop-shadow(0 0 40px rgba(139, 92, 246, 0.8));
    }
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

  /* Back to Main Page Button */
  .back-to-main-btn {
    position: fixed;
    top: 1.5rem;
    left: 1.5rem;
    background: rgba(30, 30, 40, 0.9);
    border: 2px solid rgba(139, 92, 246, 0.3);
    color: white;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 99998;
    transition: all 0.3s ease;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  }

  .back-to-main-btn:hover {
    background: rgba(30, 30, 40, 1);
    border-color: rgba(139, 92, 246, 0.6);
    transform: scale(1.1) translateX(3px);
    box-shadow: 0 6px 30px rgba(99, 102, 241, 0.6);
  }

  .back-to-main-btn svg {
    stroke: white;
  }

  /* LLM Provider Selector */
  .provider-selector {
    position: fixed;
    top: 1.5rem;
    right: 1.5rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    z-index: 99997;
    background: rgba(30, 30, 40, 0.95);
    border: 2px solid rgba(139, 92, 246, 0.4);
    border-radius: 12px;
    padding: 0.5rem 1rem;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 30px rgba(99, 102, 241, 0.3);
    transition: all 0.3s ease;
  }

  .provider-selector:hover {
    border-color: rgba(139, 92, 246, 0.7);
    box-shadow: 0 6px 30px rgba(0, 0, 0, 0.6), 0 0 40px rgba(99, 102, 241, 0.5);
    transform: translateY(-2px);
  }

  .provider-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: rgba(255, 255, 255, 0.9);
    font-size: 0.9rem;
    font-weight: 600;
    white-space: nowrap;
  }

  .provider-icon {
    font-size: 1.2rem;
    filter: drop-shadow(0 0 8px rgba(99, 102, 241, 0.6));
  }

  .provider-text {
    color: rgba(255, 255, 255, 0.8);
  }

  .provider-dropdown {
    background: rgba(20, 20, 30, 0.95);
    border: 2px solid rgba(99, 102, 241, 0.5);
    border-radius: 8px;
    padding: 0.5rem 1rem;
    color: white;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    outline: none;
    transition: all 0.3s ease;
    min-width: 140px;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23ffffff' d='M6 9L1 4h10z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 0.75rem center;
    background-size: 12px;
    padding-right: 2.5rem;
  }

  .provider-dropdown:hover {
    border-color: rgba(99, 102, 241, 0.8);
    background-color: rgba(25, 25, 35, 0.98);
    box-shadow: 0 0 20px rgba(99, 102, 241, 0.4);
  }

  .provider-dropdown:focus {
    border-color: rgba(99, 102, 241, 1);
    box-shadow: 0 0 30px rgba(99, 102, 241, 0.6);
    outline: none;
  }

  .provider-dropdown:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .provider-dropdown option {
    background: rgba(20, 20, 30, 0.98);
    color: white;
    padding: 0.5rem;
  }

  .provider-loading {
    color: rgba(99, 102, 241, 1);
    font-size: 0.85rem;
    font-weight: 600;
    animation: pulse 1.5s ease-in-out infinite;
    white-space: nowrap;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    margin-bottom: 1rem;
    padding-bottom: 1rem;
    position: relative;
    z-index: 1;
  }

  /* Search Bar Footer */
  .search-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: transparent;
    padding: 1rem 1.5rem;
    z-index: 1000;
    display: flex;
    justify-content: center;
  }

  .search-footer :global(.search-container) {
    max-width: 900px;
    width: 85%;
    margin: 0 auto;
    transform: scale(0.9);
    transform-origin: center;
  }

  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 1rem 0;
    padding-bottom: 120px; /* Space for footer */
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    max-height: calc(100vh - 200px);
    scrollbar-width: thin;
    scrollbar-color: rgba(99, 102, 241, 0.5) transparent;
    position: relative;
    z-index: 1;
  }

  .chat-messages::-webkit-scrollbar {
    width: 6px;
  }

  .chat-messages::-webkit-scrollbar-track {
    background: transparent;
  }

  .chat-messages::-webkit-scrollbar-thumb {
    background: rgba(99, 102, 241, 0.5);
    border-radius: 3px;
  }

  .chat-messages::-webkit-scrollbar-thumb:hover {
    background: rgba(99, 102, 241, 0.7);
  }


  .message {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    animation: fadeInUp 0.4s ease-out;
  }

  .user-message {
    align-items: flex-end;
  }

  .user-message .message-content {
    font-family: 'Space Grotesk', 'Poppins', sans-serif;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 18px 18px 4px 18px;
    max-width: 70%;
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.5), 0 0 30px rgba(99, 102, 241, 0.3);
    backdrop-filter: blur(10px);
    font-weight: 500;
    letter-spacing: 0.2px;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  }

  .assistant-message {
    align-items: flex-start;
  }

  .assistant-message .message-content {
    font-family: 'Inter', 'Space Grotesk', sans-serif;
    background: rgba(30, 30, 40, 0.9);
    color: var(--text-primary);
    padding: 1rem 1.5rem;
    border-radius: 18px 18px 18px 4px;
    max-width: 85%;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 30px rgba(139, 92, 246, 0.2);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(139, 92, 246, 0.3);
    font-weight: 400;
    letter-spacing: 0.1px;
    line-height: 1.7;
  }

  .assistant-message .message-content.loading {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .ai-response-text {
    font-family: 'Inter', 'Space Grotesk', sans-serif;
    margin-top: 0.5rem;
    line-height: 1.7;
    white-space: pre-wrap;
    word-wrap: break-word;
    font-weight: 400;
    letter-spacing: 0.1px;
    color: rgba(255, 255, 255, 0.95);
  }

  .error-message .message-content {
    background: rgba(239, 68, 68, 0.3);
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 12px;
    border: 1px solid rgba(239, 68, 68, 0.6);
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  
  .download-link-btn {
    display: inline-block;
    background: #10b981;
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    text-decoration: none;
    font-weight: 600;
    margin-top: 0.5rem;
    transition: all 0.2s ease;
  }
  
  .download-link-btn:hover {
    background: #059669;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.4);
  }
  
  .pdf-download-btn {
    display: inline-block;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: white;
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    text-decoration: none;
    font-weight: 600;
    margin-top: 1rem;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
    border: none;
    cursor: pointer;
    font-size: 0.9375rem;
  }
  
  .pdf-download-btn:hover {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
  }
  
  .pdf-download-btn:active {
    transform: translateY(0);
  }

  .error-icon {
    margin-right: 0.5rem;
  }

  .message-time {
    font-size: 0.75rem;
    color: rgba(255, 255, 255, 0.5);
    padding: 0 0.5rem;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(99, 102, 241, 0.3);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes fadeInDown {
    from {
      opacity: 0;
      transform: translateY(-20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
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

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @media (max-width: 768px) {
    .provider-selector {
      top: 1rem;
      right: 1rem;
      padding: 0.4rem 0.75rem;
      flex-direction: column;
      gap: 0.5rem;
    }

    .provider-label {
      font-size: 0.85rem;
    }

    .provider-dropdown {
      min-width: 120px;
      font-size: 0.9rem;
    }

    .menu-toggle {
      right: 1rem !important;
      top: 5rem !important;
    }

    .title {
      font-size: 2rem;
    }

    .title-icon {
      font-size: 2rem;
    }

    .chat-messages {
      max-height: 50vh;
    }

    .user-message .message-content,
    .assistant-message .message-content {
      max-width: 90%;
    }
  }

  /* Per-message footer */
  .message-footer {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-top: 0.4rem;
  }

  /* Hover action toolbar */
  .msg-toolbar {
    display: flex;
    gap: 0.2rem;
    opacity: 0;
    transition: opacity 0.15s ease;
  }

  .msg-hoverable:hover .msg-toolbar {
    opacity: 1;
  }

  .msg-tool-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    cursor: pointer;
    color: rgba(255, 255, 255, 0.45);
    padding: 0.25rem;
    border-radius: 5px;
    transition: color 0.15s, background 0.15s;
  }

  .msg-tool-btn:hover {
    color: #fff;
    background: rgba(139, 92, 246, 0.2);
  }

  /* Email Modal */
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.6);
    z-index: 2000;
    backdrop-filter: blur(3px);
  }

  .email-modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(20, 20, 35, 0.98);
    border: 2px solid rgba(139, 92, 246, 0.5);
    border-radius: 14px;
    padding: 0;
    width: 90%;
    max-width: 420px;
    z-index: 2001;
    box-shadow: 0 8px 40px rgba(0,0,0,0.8), 0 0 40px rgba(99,102,241,0.3);
    animation: slideDown 0.2s ease-out;
  }

  .email-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.2rem 1.5rem 1rem;
    border-bottom: 1px solid rgba(139, 92, 246, 0.2);
  }

  .email-modal-header h3 {
    margin: 0;
    color: white;
    font-size: 1.1rem;
    font-weight: 600;
  }

  .modal-close {
    background: none;
    border: none;
    color: rgba(255,255,255,0.6);
    font-size: 1.5rem;
    cursor: pointer;
    line-height: 1;
    padding: 0;
  }

  .modal-close:hover { color: white; }

  .email-modal-body {
    padding: 1.2rem 1.5rem;
    display: flex;
    flex-direction: column;
  }

  .email-label {
    color: rgba(255,255,255,0.7);
    font-size: 0.85rem;
    margin-bottom: 0.4rem;
  }

  .email-input {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(139,92,246,0.3);
    border-radius: 8px;
    padding: 0.7rem 1rem;
    color: white;
    font-size: 0.95rem;
    outline: none;
    transition: border-color 0.2s;
  }

  .email-input:focus { border-color: rgba(139,92,246,0.8); }
  .email-input::placeholder { color: rgba(255,255,255,0.3); }

  .email-type-options {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .email-type-option {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: rgba(255,255,255,0.8);
    font-size: 0.9rem;
    cursor: pointer;
  }

  .email-status {
    margin-top: 0.8rem;
    padding: 0.6rem 0.9rem;
    border-radius: 8px;
    font-size: 0.88rem;
  }

  .email-status.success {
    background: rgba(16,185,129,0.15);
    color: #10b981;
    border: 1px solid rgba(16,185,129,0.3);
  }

  .email-status.error {
    background: rgba(239,68,68,0.15);
    color: #f87171;
    border: 1px solid rgba(239,68,68,0.3);
  }

  .email-modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    padding: 1rem 1.5rem 1.2rem;
    border-top: 1px solid rgba(139,92,246,0.2);
  }

  .email-cancel-btn {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.15);
    color: rgba(255,255,255,0.7);
    padding: 0.55rem 1.2rem;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.9rem;
  }

  .email-cancel-btn:hover { background: rgba(255,255,255,0.12); }

  .email-send-btn {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border: none;
    color: white;
    padding: 0.55rem 1.4rem;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 600;
  }

  .email-send-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .email-send-btn:not(:disabled):hover {
    background: linear-gradient(135deg, #4f52e0, #7c3aed);
  }
</style>
