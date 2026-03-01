# Hakeem AI | Modern React Assistant

A state-of-the-art AI interface built with **React 19**, **Vite**, and **TypeScript**. Hakeem provides a premium chat experience with advanced Markdown support, syntax highlighting, and seamless **Model Context Protocol (MCP)** integration.

## ✨ Features

- **Modern Chat UI**: Polished glassmorphic design with smooth animations via Framer Motion.
- **Advanced Markdown**: Full support for GFM (GitHub Flavored Markdown).
- **Code Syntax Highlighting**: Professional code block rendering via `react-syntax-highlighter`.
- **MCP Hub**: Connect to multiple MCP servers over SSE (Server-Sent Events) with real-time status signals.
- **Responsive & Adaptive**: Fully optimized for mobile and desktop with a sophisticated Dark/Light theme system.
- **Smart History**: Local storage-based conversation management.

## 🚀 Deployment from Zero

Follow these instructions to get Hakeem running on a fresh device.

### 1. Prerequisites
- **Node.js**: v18.0.0 or higher ([Download](https://nodejs.org/))
- **npm**: v9.0.0 or higher (typically bundled with Node.js)

### 2. Environment Setup
Clone the project or extract the files into your desired directory.

```bash
# Enter the project folder
cd react-website
```

### 3. Installation
Install the complete dependency tree:
```bash
npm install
```

### 4. Development & Preview
To launch the development server with Hot Module Replacement (HMR):
```bash
npm run dev
```
Access the app at: `http://localhost:5173`

### 5. Production Build
To create a highly optimized, minified bundle for production:
```bash
npm run build
```
The static assets will be generated in the `dist/` directory. You can deploy this folder to any static hosting service (Vercel, Netlify, Cloudflare Pages, S3, etc.).

To preview the production build locally:
```bash
npm run preview
```

## 🛠️ Technical Stack

- **Core**: React 19, TypeScript, Vite
- **Styling**: Vanilla CSS with modern Variables, Framer Motion (Animations)
- **Messaging**: React-Markdown, Remark-GFM, React-Syntax-Highlighter (Prism)
- **Icons**: Lucide-React
- **Protocol**: Custom `useMCP` SSE Hook

## 📂 Project Structure

```text
src/
├── components/   # Shared UI (Layout, Navbar, etc.)
├── hooks/        # Custom logic (useMCP for SSE)
├── pages/        # Main views (Home, Chat, Login, etc.)
├── styles/       # Modern CSS modules and themes
└── main.tsx      # Application entry point
```

## 🔌 MCP Server Configuration

Hakeem allows dynamic connection to MCP servers.
1. Open the **Chat** interface.
2. Click the **Settings** (gear) icon in the top right.
3. Navigate to the **MCP Hub** tab.
4. Add your SSE endpoint (e.g., `http://127.0.0.1/sse`).
5. Click **Link** to establish a real-time signal.

---
© 2026 Nullnet. All rights reserved.
