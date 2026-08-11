import { defineConfig, loadEnv } from 'vite';
import { handleQwenVisionRequest } from './api/qwen-vision.js';

function qwenLocalApiPlugin(env) {
  return {
    name: 'ecosort-qwen-local-api',
    configureServer(server) {
      server.middlewares.use('/api/qwen-vision', async (request, response) => {
        const chunks = [];
        let totalBytes = 0;

        for await (const chunk of request) {
          totalBytes += chunk.length;
          if (totalBytes > 2_000_000) {
            response.statusCode = 413;
            response.setHeader('Content-Type', 'application/json; charset=utf-8');
            response.end(JSON.stringify({ error: { code: 'PayloadTooLarge' } }));
            return;
          }
          chunks.push(chunk);
        }

        let body = {};
        try {
          body = JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}');
        } catch {
          response.statusCode = 400;
          response.setHeader('Content-Type', 'application/json; charset=utf-8');
          response.end(JSON.stringify({ error: { code: 'InvalidJSON' } }));
          return;
        }

        const forwardedFor = request.headers['x-forwarded-for'];
        const result = await handleQwenVisionRequest({
          method: request.method,
          origin: request.headers.origin,
          host: request.headers.host,
          ip: String(forwardedFor || request.socket.remoteAddress || 'local').split(',')[0].trim(),
          body,
          apiKey: env.QWEN_API_KEY,
          allowedOrigins: env.QWEN_ALLOWED_ORIGINS || ''
        });

        response.statusCode = result.status;
        Object.entries(result.headers).forEach(([name, value]) => response.setHeader(name, value));
        response.end(JSON.stringify(result.body));
      });
    }
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    publicDir: 'public',
    plugins: [qwenLocalApiPlugin(env)],
    server: {
      port: 3000,
      host: true
    },
    build: {
      outDir: 'dist',
      assetsInlineLimit: 10_000
    }
  };
});
