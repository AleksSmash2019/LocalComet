import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  clearScreen: false,
  build: {
    // Split vendor chunks so HF browser / model panels lazy-load separately.
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules/svelte')) return 'svelte-vendor';
          if (id.includes('HuggingFaceBrowser') || id.includes('ModelManager')) return 'model-ui';
          return undefined;
        }
      }
    }
  },
  server: {
    host: '127.0.0.1',
    port: 1420,
    strictPort: true,
    watch: {
      // The Rust build tree is not frontend source. Watching it made the dev
      // server crash (ENOENT on target/debug/deps/*.exe) whenever cargo
      // replaced a binary mid-watch, which killed the app's page load.
      ignored: ['**/src-tauri/target/**', '**/src-tauri/gen/**']
    }
  },
  preview: {
    host: '127.0.0.1',
    port: 1421,
    strictPort: true
  }
});
