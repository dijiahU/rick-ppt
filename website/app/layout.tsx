import type { Metadata } from "next";
import "./globals.css";
import "./account.css";
import "./preview.css";
import {LanguageProvider} from './language';
export const metadata: Metadata = {metadataBase:new URL("https://rick-ppt.woodsy-crane-8759.chatgpt.site"),title:"PPTX LAB · Presentation Design Studio", description:"10 trials per account. Explore thoughtful slide design and render review. No invitation required.", robots:{index:false,follow:false},icons:{icon:"/og.png"},openGraph:{title:"PPTX LAB · Presentation Design Studio",description:"Strong content, clearly presented. 10 presentation trials per account.",images:["/og.png"]},twitter:{card:"summary_large_image",title:"PPTX LAB · Presentation Design Studio",description:"Strong content, clearly presented. 10 presentation trials per account.",images:["/og.png"]}};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="en"><body><LanguageProvider>{children}</LanguageProvider></body></html>}
