import { defineConfig } from 'vite';

export default defineConfig({
  // Thư mục 'public' được Vite serve tĩnh.
  // Mọi thứ trong này tự động copy vào 'dist/' khi build.
  // → public/tfjs_model/ sẽ thành dist/tfjs_model/ trên server
  publicDir: 'public',

  server: {
    port: 3000,
    host: true, // Cho phép iPad/Tablet cùng mạng kết nối vào
  },

  build: {
    outDir: 'dist',
    // Không inline file > 10KB thành base64 — giữ file .bin riêng
    assetsInlineLimit: 10_000,
  },
});
