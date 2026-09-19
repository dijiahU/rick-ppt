import Home from './home';
import {isAdmin} from '@/lib/admin';
export const dynamic='force-dynamic';
export default async function Page(){return <Home admin={await isAdmin()}/>;}
