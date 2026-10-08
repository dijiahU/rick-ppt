import type { Metadata } from "next";
import "./globals.css";
import "./account.css";
import "./preview.css";
import {LanguageProvider} from './language';
const configuredOrigin=process.env.SITE_ORIGIN;
const metadataBase=configuredOrigin&&configuredOrigin.startsWith('https://')?new URL(configuredOrigin):undefined;
export const metadata: Metadata = {...(metadataBase?{metadataBase}:{}),title:"rickppt · Presentation Design Studio", description:"10 trials per account. Explore thoughtful slide design and render review. No invitation required.", robots:{index:false,follow:false},icons:{icon:"/og.png"},openGraph:{title:"rickppt · Presentation Design Studio",description:"Strong content, clearly presented. 10 presentation trials per account.",images:metadataBase?["/og.png"]:[]},twitter:{card:"summary_large_image",title:"rickppt · Presentation Design Studio",description:"Strong content, clearly presented. 10 presentation trials per account.",images:metadataBase?["/og.png"]:[]}};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="en"><body><LanguageProvider>{children}</LanguageProvider></body></html>}
