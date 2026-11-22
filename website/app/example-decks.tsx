'use client';
import {useLanguage} from './language';

const REPO='https://github.com/dijiahU/rick-ppt/raw/main/examples/';
const decks=[
 {slug:'3d-printing-liquid-metal',zh:'3D 打印液态金属电子皮肤',en:'3D-printed liquid-metal e-skin',kindZh:'学术汇报 · 英文',kindEn:'Research talk',pages:15,minutes:61},
 {slug:'silk-road',zh:'丝绸之路',en:'The Silk Road',kindZh:'历史课件',kindEn:'History lesson',pages:5,minutes:37},
 {slug:'buoyancy-lesson',zh:'浮力',en:'Buoyancy',kindZh:'初二物理课件',kindEn:'Physics lesson, grade 8',pages:5,minutes:39},
 {slug:'anc-headphones-launch',zh:'降噪耳机发布',en:'Noise-cancelling headphones launch',kindZh:'发布会大屏',kindEn:'Launch event screen',pages:6,minutes:31},
 {slug:'van-gogh-starry-night',zh:'梵高《星空》',en:'Van Gogh, The Starry Night',kindZh:'艺术赏析',kindEn:'Art appreciation',pages:10,minutes:34},
 {slug:'specialty-coffee-brand',zh:'精品咖啡豆',en:'Specialty coffee beans',kindZh:'品牌介绍',kindEn:'Brand introduction',pages:8,minutes:21},
];

export default function ExampleDecks(){
 const {locale}=useLanguage(),zh=locale==='zh-CN';
 return <section className="example-decks" id="examples" aria-labelledby="example-decks-title">
  <div className="example-decks-head">
   <h2 id="example-decks-title">{zh?'这些 PPT 都是从一句需求做出来的':'Each of these started as a short brief'}</h2>
   <p>{zh?'原样交付的文件，下载后可以直接在 PowerPoint 或 WPS 里打开和修改。':'Files exactly as delivered. Download one and open it in PowerPoint or WPS.'}</p>
  </div>
  <ul>
   {decks.map(d=><li key={d.slug}>
    <a href={`${REPO}${d.slug}.pptx`} className="example-deck">
     <img src={`/examples/${d.slug}-cover.jpg`} alt={zh?`${d.zh}，封面`:`${d.en}, cover slide`} loading="lazy"/>
     <span className="example-deck-title">{zh?d.zh:d.en}</span>
     <span className="example-deck-meta">{zh?`${d.kindZh}，${d.pages} 页，用时 ${d.minutes} 分钟`:`${d.kindEn}, ${d.pages} slides, ${d.minutes} min`}</span>
     <span className="example-deck-get">{zh?'下载 PPTX':'Download PPTX'}</span>
    </a>
   </li>)}
  </ul>
 </section>;
}
