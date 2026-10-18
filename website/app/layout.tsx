import type { Metadata } from "next";
import "./globals.css";
import "./account.css";
import "./preview.css";
import {LanguageProvider} from './language';
const configuredOrigin=process.env.SITE_ORIGIN;
const metadataBase=configuredOrigin&&configuredOrigin.startsWith('https://')?new URL(configuredOrigin):undefined;
export const metadata: Metadata = {...(metadataBase?{metadataBase}:{}),title:"rickppt · Crafted, editable presentations", description:"From research figures to complete presentations: precise diagrams, editable objects and step-by-step animation in one standalone PowerPoint.", robots:{index:false,follow:false},icons:{icon:"/og.png"},openGraph:{title:"rickppt · Crafted, editable presentations",description:"Precise diagrams, native objects and step-by-step animation. Express complex ideas clearly in one PowerPoint.",images:metadataBase?["/og.png"]:[]},twitter:{card:"summary_large_image",title:"rickppt · Crafted, editable presentations",description:"Precise diagrams, native objects and step-by-step animation. Express complex ideas clearly in one PowerPoint.",images:metadataBase?["/og.png"]:[]}};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="en"><body><LanguageProvider>{children}</LanguageProvider></body></html>}
