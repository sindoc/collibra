<?xml version="1.0" encoding="UTF-8"?>
<!--
  identity.xsl — XSLT 3.0 identity + id-gen overlay transform
  Base transform for all id-gen XSL pipelines.
  Provides: identity copy, c.* ID injection, SKOS/SBVR annotation,
            Norman-Walsh-style catalog-aware document loading.
-->
<xsl:stylesheet
  xmlns:xsl  ="http://www.w3.org/1999/XSL/Transform"
  xmlns:xs   ="http://www.w3.org/2001/XMLSchema"
  xmlns:idgen="https://api-vlab.collibra.com/ontology/"
  xmlns:skos ="http://www.w3.org/2004/02/skos/core#"
  expand-text="yes"
  version="3.0">

  <!-- Deep identity copy — the Norman Walsh canonical pattern -->
  <xsl:mode on-no-match="shallow-copy"/>

  <!-- Inject idgen:id attribute on any element that already has an xml:id -->
  <xsl:template match="*[@xml:id]">
    <xsl:copy>
      <xsl:attribute name="idgen:contractRef"
        select="concat('c.ref.', @xml:id)"/>
      <xsl:apply-templates select="@*, node()"/>
    </xsl:copy>
  </xsl:template>

  <!-- Passthrough for everything else -->
  <xsl:template match="@* | node()">
    <xsl:copy>
      <xsl:apply-templates select="@*, node()"/>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
