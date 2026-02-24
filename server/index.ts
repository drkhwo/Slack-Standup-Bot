import { spawn } from 'child_process';
import { createServer } from "http";
import express from "express";

const app = express();
const httpServer = createServer(app);

// Keep the dummy web server running so Replit's health check passes
app.get('/', (req, res) => res.send('Slack Bot is running!'));

const port = parseInt(process.env.PORT || "5000", 10);
httpServer.listen(port, "0.0.0.0", () => {
  console.log(`Web server serving on port ${port}`);
  
  // Start the Python bot
  console.log('Starting Python bot...');
  const pyProcess = spawn('python3', ['main.py'], { stdio: 'inherit' });
  
  pyProcess.on('exit', (code) => {
    console.log(`Python bot exited with code ${code || 0}`);
    process.exit(code || 0);
  });
});
