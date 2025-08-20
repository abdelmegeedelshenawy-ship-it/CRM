import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Users, 
  Target, 
  Package, 
  BarChart3, 
  Settings,
  ChevronLeft,
  Building2
} from 'lucide-react';
import { cn } from '../../lib/utils';

const Sidebar = ({ isOpen, onToggle }) => {
  const location = useLocation();

  const navigation = [
    {
      name: 'Dashboard',
      href: '/dashboard',
      icon: LayoutDashboard,
    },
    {
      name: 'Clients',
      href: '/clients',
      icon: Building2,
    },
    {
      name: 'Deals',
      href: '/deals',
      icon: Target,
    },
    {
      name: 'Orders',
      href: '/orders',
      icon: Package,
    },
    {
      name: 'Analytics',
      href: '/analytics',
      icon: BarChart3,
    },
    {
      name: 'Settings',
      href: '/settings',
      icon: Settings,
    },
  ];

  return (
    <div className={cn(
      'bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transition-all duration-300 ease-in-out',
      isOpen ? 'w-64' : 'w-16'
    )}>
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className={cn(
            'flex items-center space-x-2 transition-opacity duration-200',
            isOpen ? 'opacity-100' : 'opacity-0'
          )}>
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">CRM</span>
            </div>
            <span className="font-semibold text-gray-900 dark:text-white">
              Export CRM
            </span>
          </div>
          <button
            onClick={onToggle}
            className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <ChevronLeft className={cn(
              'h-5 w-5 text-gray-500 transition-transform duration-200',
              !isOpen && 'rotate-180'
            )} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            const Icon = item.icon;
            
            return (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  'flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200'
                    : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700',
                  !isOpen && 'justify-center'
                )}
              >
                <Icon className={cn(
                  'h-5 w-5',
                  isOpen && 'mr-3'
                )} />
                <span className={cn(
                  'transition-opacity duration-200',
                  isOpen ? 'opacity-100' : 'opacity-0 w-0'
                )}>
                  {item.name}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <div className={cn(
            'text-xs text-gray-500 dark:text-gray-400 transition-opacity duration-200',
            isOpen ? 'opacity-100' : 'opacity-0'
          )}>
            <p>Export CRM Platform</p>
            <p>v1.0.0</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;

