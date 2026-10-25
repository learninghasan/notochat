import './style.css';
import {PWARegistration} from './device-notifications';
export const metadata={title:'NotoChat',description:'AI-assisted commerce workspace',manifest:'/manifest.webmanifest'};
export default function Layout({children}){return <html lang="bn"><body><PWARegistration/>{children}</body></html>}