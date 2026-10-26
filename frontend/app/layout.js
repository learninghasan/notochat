import './style.css';
import './workspace-theme.css';
import {PWARegistration} from './device-notifications';
export const metadata={title:'NotoChat',description:'AI-assisted commerce workspace',manifest:'/manifest.webmanifest'};
export default function Layout({children}){return <html lang="en"><body><PWARegistration/>{children}</body></html>}