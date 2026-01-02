import { NavLink, Outlet } from 'react-router-dom';
import {
  MessageSquare,
  Flower2,
  Upload,
  Database,
  Sparkles,
} from 'lucide-react';

const navItems = [
  { to: '/', icon: MessageSquare, label: 'Chat' },
  { to: '/garden', icon: Flower2, label: 'Wissens-Garten' },
  { to: '/upload', icon: Upload, label: 'Upload' },
];

export default function Layout() {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-midnight-900/80 backdrop-blur-sm border-r border-midnight-800 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-midnight-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-aurora-400 to-midnight-500 flex items-center justify-center">
              <Database className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-white">Adizon</h1>
              <p className="text-xs text-gray-400">Knowledge Core</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <ul className="space-y-1">
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                      isActive
                        ? 'bg-midnight-700/50 text-aurora-400 border border-midnight-600'
                        : 'text-gray-400 hover:text-white hover:bg-midnight-800/50'
                    }`
                  }
                >
                  <item.icon className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-midnight-800">
          <div className="flex items-center gap-2 px-4 py-2 text-xs text-gray-500">
            <Sparkles className="w-4 h-4" />
            <span>Sovereign AI RAG</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
