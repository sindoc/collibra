<?xml version="1.0" encoding="UTF-8"?>
<!--
  atom-aggregate.xsl — XSLT 3.0 Atom feed aggregator
  Inspired by Norman Walsh's xmlresolver + XSLT idioms (norm.walsh.name).
  Aggregates multiple Atom feeds into one, applies CSS+XSL theming,
  and emits both Atom XML and an HTML view.

  Servers: guiti.be | khakbaz.com | markupware.com | lutinio.io

  Run with Saxon-HE 12+ (XSLT 3.0):
    java -jar saxon-he.jar -xsl:atom-aggregate.xsl \
         -s:feeds.xml -o:output.atom.xml \
         catalog=deploy/catalog/catalog.xml \
         theme=css/khakbaz.css

  Or via Ant:  ant aggregate-atom
-->
<xsl:stylesheet
  xmlns:xsl   ="http://www.w3.org/1999/XSL/Transform"
  xmlns:xs    ="http://www.w3.org/2001/XMLSchema"
  xmlns:atom  ="http://www.w3.org/2005/Atom"
  xmlns:dc    ="http://purl.org/dc/terms/"
  xmlns:rdf   ="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:skos  ="http://www.w3.org/2004/02/skos/core#"
  xmlns:idgen ="https://api-vlab.collibra.com/ontology/"
  xmlns:fn    ="http://www.w3.org/2005/xpath-functions"
  xmlns:map   ="http://www.w3.org/2005/xpath-functions/map"
  xmlns:array ="http://www.w3.org/2005/xpath-functions/array"
  exclude-result-prefixes="xs fn map array"
  expand-text="yes"
  version="3.0">

  <!-- ── Parameters ────────────────────────────────────────────────────────── -->
  <xsl:param name="theme"         as="xs:string" select="'css/collibra.css'"/>
  <xsl:param name="output-html"   as="xs:boolean" select="true()"/>
  <xsl:param name="max-entries"   as="xs:integer" select="50"/>
  <xsl:param name="catalog"       as="xs:string"  select="'deploy/catalog/catalog.xml'"/>
  <xsl:param name="feed-title"    as="xs:string"  select="'id-gen Aggregated Feed'"/>
  <xsl:param name="base-url"      as="xs:string"  select="'https://markupware.com/id-gen'"/>

  <!-- ── Output: Atom XML by default ──────────────────────────────────────── -->
  <xsl:output name="atom-out"  method="xml"  indent="yes" encoding="UTF-8"/>
  <xsl:output name="html-out"  method="html" indent="yes" encoding="UTF-8"
              doctype-system="about:legacy-compat"/>

  <!-- ── Custom XSLT 3.0 functions ─────────────────────────────────────────── -->

  <!-- idgen:c-id($kind) — mint a c.* ID using XPath 3.1 -->
  <xsl:function name="idgen:c-id" as="xs:string">
    <xsl:param name="kind" as="xs:string"/>
    <!-- In full deployment, calls an extension function or external Java class -->
    <!-- Fallback: generate from timestamp + hash -->
    <xsl:variable name="ts" select="format-dateTime(current-dateTime(),
      '[Y0001][M01][D01]T[H01][m01][s01]')"/>
    <xsl:sequence select="concat('c.', $kind, '.', $ts, '-', generate-id())"/>
  </xsl:function>

  <!-- idgen:resolve-ns($prefix) — catalog namespace resolution -->
  <xsl:function name="idgen:resolve-ns" as="xs:string">
    <xsl:param name="prefix" as="xs:string"/>
    <xsl:variable name="ns-map" as="map(xs:string, xs:string)" select="map{
      'skos'  : 'http://www.w3.org/2004/02/skos/core#',
      'dcat'  : 'http://www.w3.org/ns/dcat#',
      'odrl'  : 'http://www.w3.org/ns/odrl/2/',
      'prov'  : 'http://www.w3.org/ns/prov#',
      'dc'    : 'http://purl.org/dc/terms/',
      'owl'   : 'http://www.w3.org/2002/07/owl#',
      'sbvr'  : 'https://www.omg.org/spec/SBVR/1.5/',
      'atom'  : 'http://www.w3.org/2005/Atom',
      'c'     : 'https://api-vlab.collibra.com/ontology/'
    }"/>
    <xsl:sequence select="if (map:contains($ns-map, $prefix))
                          then map:get($ns-map, $prefix)
                          else concat('urn:unknown:', $prefix)"/>
  </xsl:function>

  <!-- idgen:sbvr-check($rule) — inline SBVR rule string check -->
  <xsl:function name="idgen:sbvr-check" as="xs:boolean">
    <xsl:param name="rule" as="xs:string"/>
    <xsl:sequence select="matches($rule,
      'necessary|permitted|impossible|obligatory|forbidden', 'i')"/>
  </xsl:function>

  <!-- idgen:entry-contract-id($entry) — extract or generate contract ID -->
  <xsl:function name="idgen:entry-contract-id" as="xs:string">
    <xsl:param name="entry" as="element()"/>
    <xsl:variable name="existing" select="($entry/idgen:contractId,
                                           $entry/atom:id)[1]/string()"/>
    <xsl:sequence select="if (starts-with($existing, 'c.'))
                          then $existing
                          else idgen:c-id('contract')"/>
  </xsl:function>

  <!-- ── Main template: entry point ────────────────────────────────────────── -->
  <xsl:template match="/">
    <!-- Input: <feeds> element containing <feed href="..."/> children -->
    <xsl:variable name="all-entries" as="element()*">
      <xsl:for-each select="/feeds/feed">
        <xsl:variable name="href" select="@href"/>
        <xsl:try>
          <xsl:variable name="doc" select="doc($href)"/>
          <xsl:sequence select="$doc//atom:entry"/>
        </xsl:try>
        <xsl:catch>
          <xsl:message>WARNING: could not load feed {$href}: {$err:description}</xsl:message>
        </xsl:catch>
      </xsl:for-each>
    </xsl:variable>

    <!-- Sort by updated, take top N -->
    <xsl:variable name="sorted" as="element()*">
      <xsl:perform-sort select="$all-entries">
        <xsl:sort select="(atom:updated, atom:published)[1]" order="descending"/>
      </xsl:perform-sort>
    </xsl:variable>
    <xsl:variable name="top" select="subsequence($sorted, 1, $max-entries)"/>

    <!-- Emit aggregated Atom -->
    <xsl:result-document format="atom-out" href="{$base-url}/aggregate.atom">
      <xsl:call-template name="emit-atom">
        <xsl:with-param name="entries" select="$top"/>
      </xsl:call-template>
    </xsl:result-document>

    <!-- Emit HTML view -->
    <xsl:if test="$output-html">
      <xsl:result-document format="html-out" href="{$base-url}/aggregate.html">
        <xsl:call-template name="emit-html">
          <xsl:with-param name="entries" select="$top"/>
        </xsl:call-template>
      </xsl:result-document>
    </xsl:if>
  </xsl:template>

  <!-- ── Atom output ───────────────────────────────────────────────────────── -->
  <xsl:template name="emit-atom">
    <xsl:param name="entries" as="element()*"/>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:dc="http://purl.org/dc/terms/"
          xmlns:idgen="https://api-vlab.collibra.com/ontology/">
      <title>{$feed-title}</title>
      <id>{$base-url}/aggregate.atom</id>
      <updated>{format-dateTime(current-dateTime(),
        '[Y0001]-[M01]-[D01]T[H01]:[m01]:[s01]Z')}</updated>
      <link rel="self" href="{$base-url}/aggregate.atom"/>
      <link rel="alternate" type="text/html" href="{$base-url}/aggregate.html"/>
      <generator uri="https://github.com/sindoc/collibra">id-gen XSLT 3.0</generator>

      <xsl:for-each select="$entries">
        <xsl:variable name="cid" select="idgen:entry-contract-id(.)"/>
        <entry>
          <idgen:contractId>{$cid}</idgen:contractId>
          <xsl:copy-of select="atom:id, atom:title, atom:updated, atom:published,
                                atom:author, atom:link, atom:summary, atom:content,
                                atom:category, dc:*"/>
        </entry>
      </xsl:for-each>
    </feed>
  </xsl:template>

  <!-- ── HTML output (CSS theme applied) ───────────────────────────────────── -->
  <xsl:template name="emit-html">
    <xsl:param name="entries" as="element()*"/>
    <html lang="en">
      <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title>{$feed-title}</title>
        <!-- CSS theme (Collibra dark / khakbaz / guiti) -->
        <link rel="stylesheet" href="{$theme}"/>
        <!-- Inline fallback -->
        <style>
          :root { --bg:#0d1117; --surface:#161b22; --border:#30363d;
                  --accent:#238636; --text:#e6edf3; --muted:#8b949e; }
          body { background:var(--bg); color:var(--text);
                 font-family:'SF Mono','Fira Code',monospace; padding:2rem; }
          .feed-header h1 { color:var(--accent); margin-bottom:.25rem; }
          .entry { border:1px solid var(--border); border-radius:8px;
                   padding:1rem; margin-bottom:1rem; background:var(--surface); }
          .entry-title a { color:#58a6ff; text-decoration:none; }
          .entry-meta { font-size:.75rem; color:var(--muted); margin:.25rem 0; }
          .entry-summary { font-size:.85rem; margin-top:.5rem; }
          .contract-id { font-size:.7rem; padding:2px 8px; border-radius:12px;
                         background:#0e4429; color:#3fb950; border:1px solid #238636; }
        </style>
      </head>
      <body>
        <div class="feed-header">
          <h1>{$feed-title}</h1>
          <p class="entry-meta">Aggregated {count($entries)} entries ·
             <a href="aggregate.atom">Atom feed</a></p>
        </div>

        <xsl:for-each select="$entries">
          <xsl:variable name="cid" select="idgen:entry-contract-id(.)"/>
          <xsl:variable name="title"   select="(atom:title/string(), '(no title)')[1]"/>
          <xsl:variable name="href"    select="(atom:link[@rel='alternate']/@href,
                                                atom:link[not(@rel)]/@href,
                                                atom:id/string())[1]"/>
          <xsl:variable name="updated" select="(atom:updated, atom:published)[1]/string()"/>
          <xsl:variable name="summary" select="(atom:summary, atom:content)[1]/string()"/>
          <xsl:variable name="author"  select="atom:author/atom:name/string()"/>

          <div class="entry">
            <div class="entry-title">
              <a href="{$href}">{$title}</a>
              <xsl:text> </xsl:text>
              <span class="contract-id">{$cid}</span>
            </div>
            <div class="entry-meta">
              <xsl:if test="$author"><span>{$author} · </span></xsl:if>
              <time datetime="{$updated}">{substring($updated,1,10)}</time>
            </div>
            <xsl:if test="normalize-space($summary) ne ''">
              <div class="entry-summary">
                {substring(normalize-space($summary), 1, 280)}
                <xsl:if test="string-length(normalize-space($summary)) > 280">…</xsl:if>
              </div>
            </xsl:if>
          </div>
        </xsl:for-each>
      </body>
    </html>
  </xsl:template>

</xsl:stylesheet>
