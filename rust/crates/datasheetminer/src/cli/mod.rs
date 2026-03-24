//! CLI definitions and subcommand handlers.

pub mod deduplicate;
pub mod delete;
pub mod push;
pub mod query;
pub mod scrape;
pub mod search;

use std::path::PathBuf;

use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "datasheetminer")]
#[command(about = "Extract specs from datasheets and serve them via REST API")]
#[command(version)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,

    /// Log level (trace, debug, info, warn, error)
    #[arg(long, global = true, default_value = "info", env = "LOG_LEVEL")]
    pub log_level: String,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Scrape a datasheet URL and extract product specs
    Scrape {
        #[arg(short = 't', long)]
        product_type: Option<String>,
        #[arg(long)]
        url: Option<String>,
        #[arg(long)]
        pages: Option<String>,
        #[arg(long)]
        manufacturer: Option<String>,
        #[arg(long)]
        product_name: Option<String>,
        #[arg(long)]
        product_family: Option<String>,
        #[arg(long)]
        from_json: Option<PathBuf>,
        #[arg(long, default_value_t = 0)]
        json_index: usize,
        #[arg(long)]
        scrape_from_db: bool,
        #[arg(long)]
        scrape_all: bool,
        #[arg(short, long, default_value = "output.json")]
        output: PathBuf,
        #[arg(long, env = "GEMINI_API_KEY")]
        api_key: Option<String>,
        #[arg(long, default_value = "products")]
        table: String,
    },
    /// Search for datasheets online
    Search {
        #[arg(short = 't', long)]
        product_type: String,
        #[arg(short = 'q', long, num_args = 1..)]
        query: Vec<String>,
        #[arg(long, default_value = "duckduckgo")]
        api: String,
        #[arg(long)]
        api_key: Option<String>,
        #[arg(short, long, default_value = "search_results.json")]
        output: PathBuf,
        #[arg(long)]
        append: bool,
        #[arg(long, default_value_t = 10)]
        max_results: usize,
    },
    /// Push JSON file contents to DynamoDB
    Push {
        #[arg(long, default_value = "output.json")]
        file: PathBuf,
        #[arg(long, default_value = "products")]
        table: String,
    },
    /// Query and inspect DynamoDB contents
    Query {
        #[arg(long, default_value = "products")]
        table: String,
        #[arg(long)]
        summary: bool,
        #[arg(long)]
        list: bool,
        #[arg(long)]
        get: Option<String>,
        #[arg(long, default_value = "all")]
        product_type: String,
        #[arg(long, default_value_t = 10)]
        limit: i32,
        #[arg(long)]
        details: bool,
    },
    /// Delete items from DynamoDB
    Delete {
        #[arg(long, default_value = "products")]
        table: String,
        #[arg(long)]
        manufacturer: Option<String>,
        #[arg(long)]
        product_type: Option<String>,
        #[arg(long)]
        product_name: Option<String>,
        #[arg(long)]
        product_family: Option<String>,
        #[arg(long)]
        confirm: bool,
        #[arg(long)]
        dry_run: bool,
    },
    /// Find and remove duplicate products
    #[command(name = "dedup")]
    Deduplicate {
        #[arg(long, default_value = "products")]
        table: String,
        #[arg(long)]
        confirm: bool,
        #[arg(long)]
        dry_run: bool,
        #[arg(long)]
        json: bool,
    },
    /// Start the web server (REST API + static frontend)
    Serve {
        #[arg(long, default_value_t = 3001, env = "PORT")]
        port: u16,
        #[arg(long, default_value = "products", env = "DYNAMODB_TABLE_NAME")]
        table: String,
        #[arg(long, env = "STATIC_DIR")]
        static_dir: Option<PathBuf>,
        #[arg(long, default_value = "*", env = "CORS_ORIGIN")]
        cors_origin: String,
    },
}
